from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.work_item import WorkItem
from app.services.rca_service import get_rca
from app.services.workflow_engine import InvalidTransitionError, WorkItemStateContext


logger = get_logger(__name__)


async def _load_work_item(session: AsyncSession, work_item_id: UUID) -> WorkItem:
    res = await session.execute(select(WorkItem).where(WorkItem.id == work_item_id))
    wi = res.scalar_one_or_none()
    if wi is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WorkItem not found")
    return wi


async def transition_to_investigating(session: AsyncSession, work_item_id: UUID) -> WorkItem:
    wi = await _load_work_item(session, work_item_id)
    ctx = WorkItemStateContext(wi.status)
    try:
        new_status = ctx.transition_to_investigating()
    except InvalidTransitionError as e:
        logger.info("Invalid transition", extra={"from": e.from_status.value, "to": e.to_status.value})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    wi.status = new_status
    await session.commit()
    await session.refresh(wi)
    logger.info("State transition", extra={"work_item_id": str(wi.id), "from": ctx.status.value, "to": new_status.value})
    return wi


async def transition_to_resolved(session: AsyncSession, work_item_id: UUID) -> WorkItem:
    wi = await _load_work_item(session, work_item_id)
    ctx = WorkItemStateContext(wi.status)
    try:
        new_status = ctx.transition_to_resolved()
    except InvalidTransitionError as e:
        logger.info("Invalid transition", extra={"from": e.from_status.value, "to": e.to_status.value})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    wi.status = new_status
    await session.commit()
    await session.refresh(wi)
    logger.info("State transition", extra={"work_item_id": str(wi.id), "from": ctx.status.value, "to": new_status.value})
    return wi


async def transition_to_closed(session: AsyncSession, work_item_id: UUID) -> WorkItem:
    wi = await _load_work_item(session, work_item_id)
    ctx = WorkItemStateContext(wi.status)
    try:
        new_status = ctx.transition_to_closed()
    except InvalidTransitionError as e:
        logger.info("Invalid transition", extra={"from": e.from_status.value, "to": e.to_status.value})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    rca = await get_rca(session, work_item_id)
    if rca is None:
        logger.info("Close rejected: missing RCA", extra={"work_item_id": str(work_item_id)})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot close incident without completed RCA",
        )

    wi.status = new_status
    await session.commit()
    await session.refresh(wi)
    logger.info("State transition", extra={"work_item_id": str(wi.id), "from": ctx.status.value, "to": new_status.value})
    return wi

