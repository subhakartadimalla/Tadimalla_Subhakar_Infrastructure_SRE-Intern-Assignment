from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.rca_work_item import RCA
from app.models.work_item import WorkItem
from app.schemas.rca import RCASubmit


logger = get_logger(__name__)


def _validate_rca(payload: RCASubmit) -> float:
    if not payload.root_cause.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="root_cause is required")
    if not payload.fix_applied.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="fix_applied is required")
    if not payload.prevention_steps.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="prevention_steps is required")
    if payload.end_time <= payload.start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_time must be greater than start_time",
        )
    mttr_seconds = (payload.end_time - payload.start_time).total_seconds()
    return float(mttr_seconds)


async def get_rca(session: AsyncSession, work_item_id: UUID) -> RCA | None:
    res = await session.execute(select(RCA).where(RCA.work_item_id == work_item_id))
    return res.scalar_one_or_none()


async def create_or_update_rca(session: AsyncSession, work_item_id: UUID, payload: RCASubmit) -> RCA:
    mttr_seconds = _validate_rca(payload)

    # Ensure work item exists
    wi_res = await session.execute(select(WorkItem).where(WorkItem.id == work_item_id))
    wi = wi_res.scalar_one_or_none()
    if wi is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WorkItem not found")

    existing = await get_rca(session, work_item_id)
    if existing:
        existing.root_cause = payload.root_cause.strip()
        existing.fix_applied = payload.fix_applied.strip()
        existing.prevention_steps = payload.prevention_steps.strip()
        existing.start_time = payload.start_time
        existing.end_time = payload.end_time
        existing.mttr = mttr_seconds
        rca = existing
        action = "updated"
    else:
        rca = RCA(
            work_item_id=work_item_id,
            root_cause=payload.root_cause.strip(),
            fix_applied=payload.fix_applied.strip(),
            prevention_steps=payload.prevention_steps.strip(),
            start_time=payload.start_time,
            end_time=payload.end_time,
            mttr=mttr_seconds,
        )
        session.add(rca)
        action = "created"

    # Touch WorkItem updated_at on RCA submission
    wi.updated_at = datetime.now(UTC)

    await session.commit()
    await session.refresh(rca)
    logger.info("RCA submitted", extra={"work_item_id": str(work_item_id), "action": action, "mttr_seconds": mttr_seconds})
    return rca

