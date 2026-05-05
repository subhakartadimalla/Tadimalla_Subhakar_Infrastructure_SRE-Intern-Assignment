from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Callable
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.core.logging import get_logger
from app.models.enums import SeverityLevel, WorkItemStatus
from app.models.work_item import WorkItem


logger = get_logger(__name__)


async def _with_retries(
    op_name: str,
    fn: Callable[[], "asyncio.Future"],
    *,
    retries: int = 3,
    base_delay_s: float = 0.2,
) -> None:
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            await fn()
            return
        except Exception as exc:
            last_exc = exc
            delay = min(base_delay_s * (2 ** (attempt - 1)), 2.0)
            logger.warning("DB op retry", extra={"op": op_name, "attempt": attempt, "delay_s": delay})
            await asyncio.sleep(delay)
    logger.exception("DB op failed after retries", extra={"op": op_name})
    raise RuntimeError(f"DB op failed: {op_name}") from last_exc


async def create_work_item(
    session: AsyncSession,
    *,
    component_id: str,
    severity: SeverityLevel,
    first_signal_time: datetime,
    last_signal_time: datetime,
    title: str,
    description: str | None = None,
) -> WorkItem:
    async def _op() -> None:
        wi = WorkItem(
            component_id=component_id,
            severity=severity,
            status=WorkItemStatus.OPEN,
            title=title,
            description=description,
            first_signal_time=first_signal_time,
            last_signal_time=last_signal_time,
            signal_count=1,
        )
        session.add(wi)
        await session.commit()
        await session.refresh(wi)
        nonlocal created
        created = wi

    created: WorkItem | None = None
    await _with_retries("create_work_item", _op)
    assert created is not None
    logger.info("WorkItem created", extra={"work_item_id": str(created.id), "component_id": component_id})
    return created


async def update_work_item_signal(
    session: AsyncSession,
    *,
    work_item_id: UUID,
    last_signal_time: datetime,
    severity: SeverityLevel | None = None,
) -> WorkItem:
    async def _op() -> None:
        values: dict = {
            "last_signal_time": last_signal_time,
            "signal_count": WorkItem.signal_count + 1,
        }
        # Optional severity escalation (P0 > P1 > P2)
        if severity is not None:
            values["severity"] = severity

        await session.execute(update(WorkItem).where(WorkItem.id == work_item_id).values(**values))
        await session.commit()
        res = await session.execute(select(WorkItem).where(WorkItem.id == work_item_id))
        nonlocal updated
        updated = res.scalar_one()

    updated: WorkItem | None = None
    await _with_retries("update_work_item_signal", _op)
    assert updated is not None
    logger.info("WorkItem updated", extra={"work_item_id": str(updated.id), "signal_count": updated.signal_count})
    return updated


def now_utc() -> datetime:
    return datetime.now(UTC)

