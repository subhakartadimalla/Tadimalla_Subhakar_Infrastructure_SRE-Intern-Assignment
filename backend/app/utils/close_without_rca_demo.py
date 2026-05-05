from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import HTTPException

from app.core import database
from app.core.settings import settings
from app.models.enums import SeverityLevel, WorkItemStatus
from app.models.work_item import WorkItem
from app.services import workflow_service


async def main() -> None:
    await database.init_engine(settings.database_url)
    if database.SessionLocal is None:
        raise RuntimeError("SessionLocal not initialized")

    async with database.SessionLocal() as session:
        now = datetime.now(UTC)
        wi = WorkItem(
            component_id="CLOSE_NO_RCA_DEMO",
            severity=SeverityLevel.P2,
            status=WorkItemStatus.RESOLVED,
            title="Close without RCA demo",
            description=None,
            first_signal_time=now,
            last_signal_time=now,
            signal_count=1,
        )
        session.add(wi)
        await session.commit()
        await session.refresh(wi)

        try:
            await workflow_service.transition_to_closed(session, wi.id)
            print({"ok": False, "error": "Unexpectedly closed without RCA", "work_item_id": str(wi.id)})
        except HTTPException as e:
            print(
                {
                    "ok": True,
                    "work_item_id": str(wi.id),
                    "status_code": e.status_code,
                    "detail": e.detail,
                }
            )

    await database.close_engine()


if __name__ == "__main__":
    asyncio.run(main())

