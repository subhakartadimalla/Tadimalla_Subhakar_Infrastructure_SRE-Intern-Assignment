from __future__ import annotations

import json
from typing import Any

from redis.exceptions import RedisError

from app.core.logging import get_logger
from app.core.redis import get_redis, is_redis_available, safe_redis_call


logger = get_logger(__name__)

SIGNAL_QUEUE_KEY = "signal_queue"

_RATE_LIMIT_LUA = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local current = redis.call('INCR', key)
if current == 1 then
  redis.call('EXPIRE', key, 1)
end
return current
"""


async def get_queue_length() -> int | None:
    if not is_redis_available():
        return None
    try:
        length = await safe_redis_call("LLEN signal_queue", get_redis().llen, SIGNAL_QUEUE_KEY)
        return int(length)
    except RedisError:
        return None


async def push_signal(signal_data: dict[str, Any]) -> bool:
    """LPUSH signal payload to Redis list queue."""
    if not is_redis_available():
        return False
    payload = json.dumps(signal_data, separators=(",", ":"), ensure_ascii=False)
    try:
        await safe_redis_call("LPUSH signal_queue", get_redis().lpush, SIGNAL_QUEUE_KEY, payload)
        logger.info("Queue push", extra={"queue": SIGNAL_QUEUE_KEY})
        return True
    except RedisError:
        return False


async def pop_signal(timeout_seconds: int = 5) -> dict[str, Any] | None:
    """BRPOP signal payload from Redis list queue."""
    if not is_redis_available():
        return None
    try:
        res = await safe_redis_call("BRPOP signal_queue", get_redis().brpop, SIGNAL_QUEUE_KEY, timeout=timeout_seconds)
        if res is None:
            return None
        _key, raw = res
        logger.info("Queue pop", extra={"queue": SIGNAL_QUEUE_KEY})
        return json.loads(raw)
    except (RedisError, json.JSONDecodeError):
        logger.exception("Queue pop failed", extra={"queue": SIGNAL_QUEUE_KEY})
        return None


async def is_rate_limited(client_ip: str, limit_per_sec: int) -> bool:
    """Redis-backed fixed-window per-second rate limit."""
    if not is_redis_available():
        # If Redis is down, caller should treat as unavailable and return 503.
        raise RuntimeError("Redis not available for rate limiting")
    key = f"rate_limit:{client_ip}"
    try:
        current = await safe_redis_call(
            "EVAL rate_limit",
            get_redis().eval,
            _RATE_LIMIT_LUA,
            1,
            key,
            str(limit_per_sec),
        )
        limited = int(current) > limit_per_sec
        if limited:
            logger.info("Rate limited", extra={"client_ip": client_ip, "current": int(current), "limit": limit_per_sec})
        return limited
    except RedisError as exc:
        logger.exception("Rate limiter failed", extra={"client_ip": client_ip})
        raise RuntimeError("Redis error during rate limiting") from exc

