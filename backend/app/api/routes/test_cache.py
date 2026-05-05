from __future__ import annotations

from fastapi import APIRouter

from app.services import cache_service


router = APIRouter()


@router.post("/test/cache")
async def cache_smoke_test() -> dict[str, object]:
    component_id = "TEST_COMPONENT_01"
    work_item_id = "00000000-0000-0000-0000-000000000001"

    await cache_service.set_active_incident(component_id, work_item_id)
    active = await cache_service.get_active_incident(component_id)

    dashboard_data = [{"id": work_item_id, "component_id": component_id, "severity": "P1", "status": "OPEN"}]
    await cache_service.set_dashboard_cache(dashboard_data)
    dashboard = await cache_service.get_dashboard_cache()

    incident_obj = {"id": work_item_id, "component_id": component_id, "title": "Cache test incident"}
    await cache_service.set_incident_cache(work_item_id, incident_obj)
    incident = await cache_service.get_incident_cache(work_item_id)

    # Queue test
    await cache_service.push_signal_to_queue({"component_id": component_id, "msg": "hello"})
    queued = await cache_service.pop_signal_from_queue(timeout_seconds=1)

    return {
        "ok": True,
        "active_incident": active,
        "dashboard": dashboard,
        "incident": incident,
        "queue_item": queued,
    }

