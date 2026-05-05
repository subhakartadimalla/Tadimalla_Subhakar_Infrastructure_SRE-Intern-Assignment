from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.core import database
from app.core.logging import get_logger
from app.core.logging import configure_logging
from app.core.redis import close_redis, init_redis
from app.core.settings import settings
from app.models.enums import SeverityLevel, WorkItemStatus
from app.models.work_item import WorkItem
from app.services import cache_service
from app.services.alert_service import send_alert_non_blocking
from app.services.queue_service import pop_signal
from app.services.work_item_service import create_work_item, update_work_item_signal


logger = get_logger(__name__)


def _parse_iso(ts: str) -> datetime:
    # Accept ISO format from ingestion (payload.timestamp.isoformat()).
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _severity_from_value(v: str) -> SeverityLevel:
    return SeverityLevel(v)


def _serialize_work_item(wi: WorkItem) -> dict[str, Any]:
    return {
        "id": str(wi.id),
        "component_id": wi.component_id,
        "severity": wi.severity.value,
        "status": wi.status.value,
        "title": wi.title,
        "description": wi.description,
        "first_signal_time": wi.first_signal_time.isoformat(),
        "last_signal_time": wi.last_signal_time.isoformat(),
        "signal_count": wi.signal_count,
        "created_at": wi.created_at.isoformat(),
        "updated_at": wi.updated_at.isoformat(),
    }


async def _refresh_dashboard_cache(session) -> None:
    # Keep it small: active incidents (not CLOSED), sorted by severity then updated_at.
    res = await session.execute(
        select(WorkItem)
        .where(WorkItem.status != WorkItemStatus.CLOSED)
        .order_by(WorkItem.severity.asc(), WorkItem.updated_at.desc())
        .limit(50)
    )
    items = res.scalars().all()
    payload = [_serialize_work_item(wi) for wi in items]
    await cache_service.set_dashboard_cache(payload)


async def process_signal(signal: dict[str, Any]) -> None:
    component_id = str(signal.get("component_id", "")).strip()
    if not component_id:
        logger.warning("Dropping invalid signal (missing component_id)")
        return

    lock_token = await cache_service.acquire_component_lock(component_id, ttl_seconds=8)
    if not lock_token:
        # Another worker is likely handling this component; requeue for later.
        await cache_service.push_signal_to_queue(signal)
        return

    try:
        if database.SessionLocal is None:
            raise RuntimeError("SessionLocal not initialized")

        ts = _parse_iso(str(signal["timestamp"]))
        severity = _severity_from_value(str(signal["severity"]))

        async with database.SessionLocal() as session:
            # Debounce: active_incident cache
            existing_id = await cache_service.check_duplicate_signal(component_id)

            if existing_id:
                wi_id = UUID(existing_id)
                wi = await update_work_item_signal(
                    session,
                    work_item_id=wi_id,
                    last_signal_time=ts,
                    severity=severity,
                )
                logger.info("Signal attached to existing WorkItem", extra={"work_item_id": existing_id})
            else:
                wi = await create_work_item(
                    session,
                    component_id=component_id,
                    severity=severity,
                    first_signal_time=ts,
                    last_signal_time=ts,
                    title=signal.get("message", "Signal"),
                    description=None,
                )
                await cache_service.set_debounce_key(component_id, str(wi.id))
                # Trigger alert ONLY on new WorkItem creation (async, non-blocking).
                asyncio.create_task(send_alert_non_blocking(wi))

            # Store raw signals in Redis (NoSQL-like list)
            await cache_service.append_raw_signal(str(wi.id), signal)

            # Invalidate incident detail cache so the next API read rebuilds it
            # with complete data (WorkItem + signals + RCA).  Writing a partial
            # entry here (WorkItem only, no signals) would cause the API to
            # return an empty signals list until the TTL expires.
            await cache_service.invalidate_incident_cache(str(wi.id))

            # Update dashboard cache
            await _refresh_dashboard_cache(session)

    except Exception:
        logger.exception("Worker failed processing signal; requeueing")
        # Requeue on failure (best-effort)
        await cache_service.push_signal_to_queue(signal)
    finally:
        await cache_service.release_component_lock(component_id, lock_token)


async def run_worker() -> None:
    configure_logging(settings.log_level, service="ims-worker")
    await database.init_engine(settings.database_url)
    await init_redis(settings.redis_url)
    logger.info("Signal worker started")

    try:
        while True:
            item = await pop_signal(timeout_seconds=5)
            if item is None:
                continue
            await process_signal(item)
    finally:
        await close_redis()
        await database.close_engine()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()

