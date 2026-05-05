from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import SeverityLevel, WorkItemStatus
from app.models.work_item import WorkItem


async def create_sample_work_item(session: AsyncSession) -> WorkItem:
    """Insert one sample incident with no RCA, for local/demo usage."""
    now = datetime.now(UTC)
    work_item = WorkItem(
        component_id="RDBMS_PRIMARY_01",
        severity=SeverityLevel.P0,
        status=WorkItemStatus.OPEN,
        title="Database connectivity errors",
        description="Elevated connection timeouts and failed queries.",
        first_signal_time=now,
        last_signal_time=now,
        signal_count=1,
    )
    session.add(work_item)
    await session.commit()
    await session.refresh(work_item)
    return work_item

