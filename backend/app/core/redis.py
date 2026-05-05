from __future__ import annotations

import asyncio
import random
from typing import AsyncIterator

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.logging import get_logger
from app.core.settings import settings


_redis: Redis | None = None
logger = get_logger(__name__)


async def init_redis(redis_url: str) -> None:
    global _redis
    if _redis is not None:
        return
    logger.info("Initializing Redis client", extra={"redis_url": redis_url})

    # ConnectionPool is created implicitly by redis-py when using from_url.
    _redis = Redis.from_url(
        redis_url,
        decode_responses=True,
        socket_connect_timeout=settings.redis_connect_timeout_seconds,
        socket_timeout=settings.redis_socket_timeout_seconds,
        health_check_interval=10,
        retry_on_timeout=True,
    )

    last_exc: Exception | None = None
    for attempt in range(1, settings.redis_max_retries + 1):
        try:
            await _redis.ping()
            logger.info("Redis connection OK", extra={"attempt": attempt})
            return
        except Exception as exc:
            last_exc = exc
            # Exponential backoff with jitter
            delay = (settings.redis_retry_base_delay_ms / 1000.0) * (2 ** (attempt - 1))
            delay = min(delay, 5.0) * (0.8 + 0.4 * random.random())
            logger.warning(
                "Redis connection retry",
                extra={"attempt": attempt, "max_retries": settings.redis_max_retries, "delay_s": delay},
            )
            await asyncio.sleep(delay)

    logger.exception("Redis connection FAILED", extra={"redis_url": redis_url})
    raise RuntimeError("Redis unavailable") from last_exc


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        logger.info("Closing Redis client")
        try:
            # redis-py asyncio client supports `aclose()` in newer versions.
            aclose = getattr(_redis, "aclose", None)
            if callable(aclose):
                await aclose()
            else:
                await _redis.close()
        except Exception:
            logger.exception("Failed closing Redis client")
    _redis = None


def get_redis() -> Redis:
    if _redis is None:
        raise RuntimeError("Redis not initialized")
    return _redis


async def get_redis_dep() -> AsyncIterator[Redis]:
    """FastAPI dependency. Yields a shared async Redis client."""
    yield get_redis()


def is_redis_available() -> bool:
    return _redis is not None


async def safe_redis_call(op_name: str, fn, *args, **kwargs):
    """
    Execute a redis call safely.

    - Logs failures
    - Raises RedisError to the caller (services may choose to fallback)
    """
    try:
        return await fn(*args, **kwargs)
    except RedisError:
        logger.exception("Redis operation failed", extra={"op": op_name})
        raise

