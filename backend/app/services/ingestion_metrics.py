from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.core.logging import get_logger
from app.services.queue_service import get_queue_length


logger = get_logger(__name__)


@dataclass
class IngestionCounters:
    accepted: int = 0
    rejected_rate_limited: int = 0
    rejected_backpressure: int = 0
    rejected_redis_down: int = 0


_counters = IngestionCounters()
_lock = asyncio.Lock()


async def inc_accepted() -> None:
    async with _lock:
        _counters.accepted += 1


async def inc_rejected_rate_limited() -> None:
    async with _lock:
        _counters.rejected_rate_limited += 1


async def inc_rejected_backpressure() -> None:
    async with _lock:
        _counters.rejected_backpressure += 1


async def inc_rejected_redis_down() -> None:
    async with _lock:
        _counters.rejected_redis_down += 1


async def snapshot_and_reset() -> IngestionCounters:
    async with _lock:
        snap = IngestionCounters(**_counters.__dict__)
        _counters.accepted = 0
        _counters.rejected_rate_limited = 0
        _counters.rejected_backpressure = 0
        _counters.rejected_redis_down = 0
        return snap


async def metrics_loop(interval_seconds: int = 5) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        snap = await snapshot_and_reset()
        queue_len = await get_queue_length()
        total = (
            snap.accepted
            + snap.rejected_rate_limited
            + snap.rejected_backpressure
            + snap.rejected_redis_down
        )
        signals_per_sec = snap.accepted / interval_seconds
        logger.info(
            "Ingestion metrics",
            extra={
                "interval_s": interval_seconds,
                "accepted": snap.accepted,
                "rejected_rate_limited": snap.rejected_rate_limited,
                "rejected_backpressure": snap.rejected_backpressure,
                "rejected_redis_down": snap.rejected_redis_down,
                "total_requests": total,
                "signals_per_sec": signals_per_sec,
                "queue_length": queue_len,
            },
        )

