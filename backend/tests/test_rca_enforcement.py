from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from app.core import database
from app.core.settings import settings
from app.models.enums import SeverityLevel, WorkItemStatus
from app.models.work_item import WorkItem
from app.schemas.rca import RCASubmit
from app.services import rca_service, workflow_service


@pytest.mark.asyncio(scope="session")
async def test_close_without_rca_fails() -> None:
    await database.init_engine(settings.database_url)
    assert database.SessionLocal is not None

    async with database.SessionLocal() as session:
        now = datetime.now(UTC)
        wi = WorkItem(
            component_id="RCA_TEST_NO_RCA",
            severity=SeverityLevel.P2,
            status=WorkItemStatus.RESOLVED,
            title="t",
            description=None,
            first_signal_time=now,
            last_signal_time=now,
            signal_count=1,
        )
        session.add(wi)
        await session.commit()
        await session.refresh(wi)

        with pytest.raises(HTTPException) as e:
            await workflow_service.transition_to_closed(session, wi.id)
        assert e.value.status_code == 400
        assert "Cannot close incident without completed RCA" in str(e.value.detail)


@pytest.mark.asyncio(scope="session")
async def test_incomplete_rca_fails() -> None:
    await database.init_engine(settings.database_url)
    assert database.SessionLocal is not None

    async with database.SessionLocal() as session:
        now = datetime.now(UTC)
        wi = WorkItem(
            component_id="RCA_TEST_BAD_RCA",
            severity=SeverityLevel.P2,
            status=WorkItemStatus.RESOLVED,
            title="t",
            description=None,
            first_signal_time=now,
            last_signal_time=now,
            signal_count=1,
        )
        session.add(wi)
        await session.commit()
        await session.refresh(wi)

        bad = RCASubmit(
            # Pass pydantic min_length, but fail service-level strip() validation.
            root_cause="   ",
            fix_applied="x",
            prevention_steps="y",
            start_time=now,
            end_time=now + timedelta(minutes=5),
        )
        with pytest.raises(HTTPException) as e:
            await rca_service.create_or_update_rca(session, wi.id, bad)
        assert e.value.status_code == 400


@pytest.mark.asyncio(scope="session")
async def test_valid_rca_then_close_success_and_mttr() -> None:
    await database.init_engine(settings.database_url)
    assert database.SessionLocal is not None

    async with database.SessionLocal() as session:
        now = datetime.now(UTC)
        wi = WorkItem(
            component_id="RCA_TEST_GOOD",
            severity=SeverityLevel.P2,
            status=WorkItemStatus.RESOLVED,
            title="t",
            description=None,
            first_signal_time=now,
            last_signal_time=now,
            signal_count=1,
        )
        session.add(wi)
        await session.commit()
        await session.refresh(wi)

        payload = RCASubmit(
            root_cause="Network partition",
            fix_applied="Restarted service",
            prevention_steps="Add circuit breaker",
            start_time=now,
            end_time=now + timedelta(minutes=10),
        )
        rca = await rca_service.create_or_update_rca(session, wi.id, payload)
        assert rca.mttr == pytest.approx(600.0, rel=0.001)

        closed = await workflow_service.transition_to_closed(session, wi.id)
        assert closed.status == WorkItemStatus.CLOSED

