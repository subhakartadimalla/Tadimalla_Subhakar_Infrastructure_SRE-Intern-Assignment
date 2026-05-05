from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.core.logging import get_logger
from app.services.queue_service import get_queue_length


logger = get_logger(__name__)


@dataclass
class Counters:
    signals_ingested: int = 0
    rejected_rate_limited: int = 0
    rejected_backpressure: int = 0
    rejected_redis_down: int = 0


_counters = Counters()
_lock = asyncio.Lock()


async def inc_signals_ingested() -> None:
    async with _lock:
        _counters.signals_ingested += 1


async def inc_rejected_rate_limited() -> None:
    async with _lock:
        _counters.rejected_rate_limited += 1


async def inc_rejected_backpressure() -> None:
    async with _lock:
        _counters.rejected_backpressure += 1


async def inc_rejected_redis_down() -> None:
    async with _lock:
        _counters.rejected_redis_down += 1


async def _snapshot_and_reset() -> Counters:
    async with _lock:
        snap = Counters(**_counters.__dict__)
        _counters.signals_ingested = 0
        _counters.rejected_rate_limited = 0
        _counters.rejected_backpressure = 0
        _counters.rejected_redis_down = 0
        return snap


async def metrics_loop(interval_seconds: int = 5) -> None:
    """Logs throughput + queue size every interval."""
    while True:
        await asyncio.sleep(interval_seconds)
        snap = await _snapshot_and_reset()
        queue_len = await get_queue_length()
        signals_per_sec = snap.signals_ingested / interval_seconds

        logger.info(
            "Throughput metrics",
            extra={
                "interval_s": interval_seconds,
                "signals_ingested": snap.signals_ingested,
                "signals_per_sec": signals_per_sec,
                "rejected_rate_limited": snap.rejected_rate_limited,
                "rejected_backpressure": snap.rejected_backpressure,
                "rejected_redis_down": snap.rejected_redis_down,
                "queue_length": queue_len,
            },
        )

