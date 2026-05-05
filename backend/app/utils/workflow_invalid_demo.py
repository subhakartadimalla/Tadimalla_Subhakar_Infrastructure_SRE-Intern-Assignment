from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import HTTPException

from app.core import database
from app.core.settings import settings
from app.models.enums import SeverityLevel, WorkItemStatus
from app.models.work_item import WorkItem
from app.services import workflow_service


async def _create_work_item(session, status: WorkItemStatus) -> WorkItem:
    now = datetime.now(UTC)
    wi = WorkItem(
        component_id="WORKFLOW_INVALID_DEMO",
        severity=SeverityLevel.P2,
        status=status,
        title=f"Invalid demo ({status.value})",
        description=None,
        first_signal_time=now,
        last_signal_time=now,
        signal_count=1,
    )
    session.add(wi)
    await session.commit()
    await session.refresh(wi)
    return wi


async def main() -> None:
    await database.init_engine(settings.database_url)
    if database.SessionLocal is None:
        raise RuntimeError("SessionLocal not initialized")

    results: list[dict[str, object]] = []

    async with database.SessionLocal() as session:
        # 1) OPEN -> CLOSED (invalid)
        wi_open = await _create_work_item(session, WorkItemStatus.OPEN)
        try:
            await workflow_service.transition_to_closed(session, wi_open.id)
        except HTTPException as e:
            results.append(
                {
                    "case": "OPEN -> CLOSED",
                    "status_code": e.status_code,
                    "detail": e.detail,
                }
            )

        # 2) RESOLVED -> INVESTIGATING (invalid)
        wi_resolved = await _create_work_item(session, WorkItemStatus.RESOLVED)
        try:
            await workflow_service.transition_to_investigating(session, wi_resolved.id)
        except HTTPException as e:
            results.append(
                {
                    "case": "RESOLVED -> INVESTIGATING",
                    "status_code": e.status_code,
                    "detail": e.detail,
                }
            )

        # 3) CLOSED -> RESOLVED (invalid; closed has no transitions)
        wi_closed = await _create_work_item(session, WorkItemStatus.CLOSED)
        try:
            await workflow_service.transition_to_resolved(session, wi_closed.id)
        except HTTPException as e:
            results.append(
                {
                    "case": "CLOSED -> RESOLVED",
                    "status_code": e.status_code,
                    "detail": e.detail,
                }
            )

    await database.close_engine()
    print({"invalid_transition_results": results})


if __name__ == "__main__":
    asyncio.run(main())

