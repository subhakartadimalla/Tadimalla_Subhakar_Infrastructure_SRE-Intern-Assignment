from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core import database
from app.core.redis import close_redis, init_redis
from app.core.settings import settings
from app.models.enums import SeverityLevel, WorkItemStatus
from app.models.work_item import WorkItem
from app.services import cache_service, incident_service


@pytest.mark.asyncio(scope="session")
async def test_dashboard_cache_set_on_miss() -> None:
    await database.init_engine(settings.database_url)
    await init_redis(settings.redis_url)
    assert database.SessionLocal is not None

    await cache_service.invalidate_dashboard_cache()

    async with database.SessionLocal() as session:
        data = await incident_service.list_active_incidents_cached(session)
        assert isinstance(data, list)

        cached = await cache_service.get_dashboard_cache()
        assert cached is not None

    await close_redis()
    await database.close_engine()


@pytest.mark.asyncio(scope="session")
async def test_incident_detail_includes_signals_and_sets_cache() -> None:
    await database.init_engine(settings.database_url)
    await init_redis(settings.redis_url)
    assert database.SessionLocal is not None

    async with database.SessionLocal() as session:
        now = datetime.now(UTC)
        wi = WorkItem(
            component_id="INCIDENT_DETAIL_CACHE_TEST",
            severity=SeverityLevel.P2,
            status=WorkItemStatus.OPEN,
            title="t",
            description=None,
            first_signal_time=now,
            last_signal_time=now,
            signal_count=1,
        )
        session.add(wi)
        await session.commit()
        await session.refresh(wi)

        await cache_service.invalidate_incident_cache(str(wi.id))
        await cache_service.append_raw_signal(str(wi.id), {"component_id": wi.component_id, "severity": "P2"})

        detail = await incident_service.get_incident_detail_cached(session, wi.id)
        assert detail["id"] == str(wi.id)
        assert isinstance(detail["signals"], list)
        assert len(detail["signals"]) >= 1

        cached = await cache_service.get_incident_cache(str(wi.id))
        assert cached is not None

    await close_redis()
    await database.close_engine()

