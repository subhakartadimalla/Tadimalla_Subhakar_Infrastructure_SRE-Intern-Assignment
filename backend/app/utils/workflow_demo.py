from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from app.core import database
from app.core.settings import settings
from app.models.enums import SeverityLevel, WorkItemStatus
from app.models.work_item import WorkItem
from app.services import workflow_service


async def _fetch_status(session, work_item_id) -> WorkItemStatus:
    res = await session.execute(select(WorkItem).where(WorkItem.id == work_item_id))
    wi = res.scalar_one()
    return wi.status


async def main() -> None:
    await database.init_engine(settings.database_url)
    if database.SessionLocal is None:
        raise RuntimeError("SessionLocal not initialized")

    async with database.SessionLocal() as session:
        now = datetime.now(UTC)
        wi = WorkItem(
            component_id="WORKFLOW_DEMO_COMPONENT",
            severity=SeverityLevel.P2,
            status=WorkItemStatus.OPEN,
            title="Workflow demo",
            description=None,
            first_signal_time=now,
            last_signal_time=now,
            signal_count=1,
        )
        session.add(wi)
        await session.commit()
        await session.refresh(wi)

        out: list[dict[str, str]] = []

        out.append({"step": "created", "status": (await _fetch_status(session, wi.id)).value})

        wi = await workflow_service.transition_to_investigating(session, wi.id)
        out.append({"step": "to_investigating", "status": (await _fetch_status(session, wi.id)).value})

        wi = await workflow_service.transition_to_resolved(session, wi.id)
        out.append({"step": "to_resolved", "status": (await _fetch_status(session, wi.id)).value})

        wi = await workflow_service.transition_to_closed(session, wi.id)
        out.append({"step": "to_closed", "status": (await _fetch_status(session, wi.id)).value})

        print({"work_item_id": str(wi.id), "transitions": out})

    await database.close_engine()


if __name__ == "__main__":
    asyncio.run(main())

