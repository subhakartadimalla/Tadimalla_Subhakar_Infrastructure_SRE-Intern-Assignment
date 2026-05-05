from __future__ import annotations

import json
from typing import Any

from redis.exceptions import RedisError

from app.core.logging import get_logger
from app.core.redis import get_redis, is_redis_available, safe_redis_call
from app.core.settings import settings


logger = get_logger(__name__)


def _key_active_incident(component_id: str) -> str:
    return f"active_incident:{component_id}"


def _key_incident(work_item_id: str) -> str:
    return f"incident:{work_item_id}"


KEY_DASHBOARD_ACTIVE = "dashboard:active_incidents"
KEY_SIGNAL_QUEUE = "signal_queue"


def _key_raw_signals(work_item_id: str) -> str:
    return f"signals:{work_item_id}"


def _key_lock(component_id: str) -> str:
    return f"lock:{component_id}"


# ----------------------------
# Active incident debounce cache
# ----------------------------
async def get_active_incident(component_id: str) -> str | None:
    if not is_redis_available():
        return None
    key = _key_active_incident(component_id)
    try:
        value = await safe_redis_call("GET active_incident", get_redis().get, key)
        if value:
            logger.info("Cache hit", extra={"cache": "active_incident", "component_id": component_id})
        else:
            logger.info("Cache miss", extra={"cache": "active_incident", "component_id": component_id})
        return value
    except RedisError:
        return None


async def set_active_incident(component_id: str, work_item_id: str, ttl_seconds: int | None = None) -> bool:
    if not is_redis_available():
        return False
    key = _key_active_incident(component_id)
    ttl = ttl_seconds or settings.debounce_window_seconds
    try:
        await safe_redis_call("SETEX active_incident", get_redis().setex, key, ttl, work_item_id)
        logger.info(
            "Cache write",
            extra={"cache": "active_incident", "component_id": component_id, "ttl_s": ttl},
        )
        return True
    except RedisError:
        return False


# ----------------------------
# Dashboard cache
# ----------------------------
async def get_dashboard_cache() -> list[dict[str, Any]] | None:
    if not is_redis_available():
        return None
    try:
        raw = await safe_redis_call("GET dashboard", get_redis().get, KEY_DASHBOARD_ACTIVE)
        if not raw:
            logger.info("Cache miss", extra={"cache": "dashboard"})
            return None
        logger.info("Cache hit", extra={"cache": "dashboard"})
        return json.loads(raw)
    except (RedisError, json.JSONDecodeError):
        logger.exception("Dashboard cache read failed")
        return None


async def set_dashboard_cache(data: list[dict[str, Any]], ttl_seconds: int | None = None) -> bool:
    if not is_redis_available():
        return False
    ttl = ttl_seconds or settings.dashboard_cache_ttl_seconds
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    try:
        await safe_redis_call("SETEX dashboard", get_redis().setex, KEY_DASHBOARD_ACTIVE, ttl, payload)
        logger.info("Cache write", extra={"cache": "dashboard", "ttl_s": ttl, "items": len(data)})
        return True
    except RedisError:
        return False


# ----------------------------
# Incident detail cache
# ----------------------------
async def get_incident_cache(work_item_id: str) -> dict[str, Any] | None:
    if not is_redis_available():
        return None
    key = _key_incident(work_item_id)
    try:
        raw = await safe_redis_call("GET incident", get_redis().get, key)
        if not raw:
            logger.info("Cache miss", extra={"cache": "incident", "work_item_id": work_item_id})
            return None
        logger.info("Cache hit", extra={"cache": "incident", "work_item_id": work_item_id})
        return json.loads(raw)
    except (RedisError, json.JSONDecodeError):
        logger.exception("Incident cache read failed", extra={"work_item_id": work_item_id})
        return None


async def set_incident_cache(work_item_id: str, data: dict[str, Any], ttl_seconds: int | None = None) -> bool:
    if not is_redis_available():
        return False
    key = _key_incident(work_item_id)
    ttl = ttl_seconds or settings.incident_cache_ttl_seconds
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    try:
        await safe_redis_call("SETEX incident", get_redis().setex, key, ttl, payload)
        logger.info("Cache write", extra={"cache": "incident", "work_item_id": work_item_id, "ttl_s": ttl})
        return True
    except RedisError:
        return False


# ----------------------------
# Debouncing helpers (signals)
# ----------------------------
async def check_duplicate_signal(component_id: str) -> str | None:
    """Return existing work_item_id if a debounce key is still active."""
    return await get_active_incident(component_id)


async def set_debounce_key(component_id: str, work_item_id: str) -> bool:
    """Set debounce key with TTL = debounce window seconds."""
    return await set_active_incident(component_id, work_item_id, ttl_seconds=settings.debounce_window_seconds)


# ----------------------------
# Simple Redis list queue
# ----------------------------
async def push_signal_to_queue(signal_data: dict[str, Any]) -> bool:
    if not is_redis_available():
        return False
    payload = json.dumps(signal_data, separators=(",", ":"), ensure_ascii=False)
    try:
        await safe_redis_call("LPUSH signal_queue", get_redis().lpush, KEY_SIGNAL_QUEUE, payload)
        logger.info("Queue push", extra={"queue": KEY_SIGNAL_QUEUE})
        return True
    except RedisError:
        return False


async def pop_signal_from_queue(timeout_seconds: int = 5) -> dict[str, Any] | None:
    if not is_redis_available():
        return None
    try:
        res = await safe_redis_call("BRPOP signal_queue", get_redis().brpop, KEY_SIGNAL_QUEUE, timeout=timeout_seconds)
        if res is None:
            return None
        _key, raw = res
        logger.info("Queue pop", extra={"queue": KEY_SIGNAL_QUEUE})
        return json.loads(raw)
    except (RedisError, json.JSONDecodeError):
        logger.exception("Queue pop failed", extra={"queue": KEY_SIGNAL_QUEUE})
        return None


# ----------------------------
# Raw signal storage (NoSQL-like)
# ----------------------------
async def append_raw_signal(work_item_id: str, signal_data: dict[str, Any], max_len: int = 2000) -> bool:
    """
    Append raw signal JSON to Redis list `signals:{work_item_id}`.
    Uses a capped list to avoid unbounded memory growth.
    """
    if not is_redis_available():
        return False
    key = _key_raw_signals(work_item_id)
    payload = json.dumps(signal_data, separators=(",", ":"), ensure_ascii=False)
    try:
        pipe = get_redis().pipeline()
        pipe.lpush(key, payload)
        pipe.ltrim(key, 0, max_len - 1)
        await safe_redis_call("PIPE raw_signals", pipe.execute)
        return True
    except RedisError:
        return False


async def get_raw_signals(work_item_id: str, limit: int = 200) -> list[dict[str, Any]]:
    """Fetch most recent raw signals for a WorkItem from Redis list."""
    if not is_redis_available():
        return []
    key = _key_raw_signals(work_item_id)
    try:
        raw_items = await safe_redis_call("LRANGE raw_signals", get_redis().lrange, key, 0, max(0, limit - 1))
        out: list[dict[str, Any]] = []
        for raw in raw_items:
            try:
                out.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        return out
    except RedisError:
        return []


async def invalidate_dashboard_cache() -> bool:
    if not is_redis_available():
        return False
    try:
        await safe_redis_call("DEL dashboard", get_redis().delete, KEY_DASHBOARD_ACTIVE)
        return True
    except RedisError:
        return False


async def invalidate_incident_cache(work_item_id: str) -> bool:
    if not is_redis_available():
        return False
    key = _key_incident(work_item_id)
    try:
        await safe_redis_call("DEL incident", get_redis().delete, key)
        return True
    except RedisError:
        return False


# ----------------------------
# Component lock (multi-worker safety)
# ----------------------------
async def acquire_component_lock(component_id: str, ttl_seconds: int = 8) -> str | None:
    """Acquire a best-effort lock for a component; returns lock token if acquired."""
    if not is_redis_available():
        return None
    token = str(__import__("uuid").uuid4())
    key = _key_lock(component_id)
    try:
        ok = await safe_redis_call("SET lock", get_redis().set, key, token, ex=ttl_seconds, nx=True)
        if ok:
            return token
        return None
    except RedisError:
        return None


async def release_component_lock(component_id: str, token: str) -> bool:
    """Release lock only if token matches (Lua compare-and-del)."""
    if not is_redis_available():
        return False
    key = _key_lock(component_id)
    lua = "if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('DEL',KEYS[1]) else return 0 end"
    try:
        res = await safe_redis_call("EVAL unlock", get_redis().eval, lua, 1, key, token)
        return int(res) == 1
    except RedisError:
        return False

