from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.enums import SeverityLevel, WorkItemStatus
from app.models.work_item import WorkItem
from app.services import cache_service
from app.services.rca_service import get_rca


logger = get_logger(__name__)


def _severity_rank_expr():
    return case(
        (WorkItem.severity == SeverityLevel.P0, 0),
        (WorkItem.severity == SeverityLevel.P1, 1),
        (WorkItem.severity == SeverityLevel.P2, 2),
        else_=9,
    )


def _dashboard_item(wi: WorkItem) -> dict[str, Any]:
    return {
        "id": str(wi.id),
        "component_id": wi.component_id,
        "severity": wi.severity.value,
        "status": wi.status.value,
        "signal_count": wi.signal_count,
        "last_updated": wi.updated_at.isoformat(),
    }


def _work_item_detail(wi: WorkItem) -> dict[str, Any]:
    return {
        "id": str(wi.id),
        "component_id": wi.component_id,
        "severity": wi.severity.value,
        "status": wi.status.value,
        "title": wi.title,
        "description": wi.description,
        "signal_count": wi.signal_count,
        "first_signal_time": wi.first_signal_time.isoformat(),
        "last_signal_time": wi.last_signal_time.isoformat(),
        "created_at": wi.created_at.isoformat(),
        "updated_at": wi.updated_at.isoformat(),
    }


async def list_active_incidents(session: AsyncSession) -> list[dict[str, Any]]:
    res = await session.execute(
        select(WorkItem)
        .where(WorkItem.status != WorkItemStatus.CLOSED)
        .order_by(_severity_rank_expr().asc(), WorkItem.updated_at.desc())
        .limit(100)
    )
    items = res.scalars().all()
    return [_dashboard_item(wi) for wi in items]


async def get_incident_detail(session: AsyncSession, work_item_id: UUID) -> dict[str, Any]:
    res = await session.execute(select(WorkItem).where(WorkItem.id == work_item_id))
    wi = res.scalar_one_or_none()
    if wi is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WorkItem not found")

    signals = await cache_service.get_raw_signals(str(work_item_id), limit=200)
    rca = await get_rca(session, work_item_id)
    rca_dict = None
    if rca is not None:
        rca_dict = {
            "work_item_id": str(rca.work_item_id),
            "root_cause": rca.root_cause,
            "fix_applied": rca.fix_applied,
            "prevention_steps": rca.prevention_steps,
            "start_time": rca.start_time.isoformat(),
            "end_time": rca.end_time.isoformat(),
            "mttr": rca.mttr,
        }

    return {**_work_item_detail(wi), "signals": signals, "rca": rca_dict}


async def list_active_incidents_cached(session: AsyncSession) -> list[dict[str, Any]]:
    cached = await cache_service.get_dashboard_cache()
    if cached is not None:
        return cached
    data = await list_active_incidents(session)
    await cache_service.set_dashboard_cache(data)
    return data


async def get_incident_detail_cached(session: AsyncSession, work_item_id: UUID) -> dict[str, Any]:
    cached = await cache_service.get_incident_cache(str(work_item_id))
    if cached is not None:
        # If cached entry has no signals, it may have been written before the worker
        # processed the queue. Treat it as a miss so fresh signal data is served.
        if cached.get("signals"):
            return cached
        logger.info(
            "Cache hit but no signals — bypassing stale cache",
            extra={"work_item_id": str(work_item_id)},
        )

    data = await get_incident_detail(session, work_item_id)
    # If the incident is extremely fresh the worker may not have appended signals yet.
    # Retry up to 3 times with short back-off before giving up and caching.
    if not data.get("signals"):
        for delay in (0.3, 0.6, 1.0):
            await asyncio.sleep(delay)
            data = await get_incident_detail(session, work_item_id)
            if data.get("signals"):
                break

    # Only cache once we have signals (or the incident genuinely has none).
    # If still empty, skip caching so the next request tries again.
    if data.get("signals"):
        await cache_service.set_incident_cache(str(work_item_id), data)
    return data

