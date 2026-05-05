from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.services import cache_service, incident_service, workflow_service


router = APIRouter(prefix="/incidents", tags=["incidents"])
logger = get_logger(__name__)


class StateChangeRequest(BaseModel):
    action: str = Field(pattern="^(INVESTIGATING|RESOLVED|CLOSED)$")


@router.get("")
async def list_incidents(session: AsyncSession = Depends(get_db)):
    logger.info("GET /incidents")
    return await incident_service.list_active_incidents_cached(session)


@router.get("/{id}")
async def get_incident(id: UUID, session: AsyncSession = Depends(get_db)):
    logger.info("GET /incidents/{id}", extra={"work_item_id": str(id)})
    return await incident_service.get_incident_detail_cached(session, id)


@router.post("/{id}/state")
async def change_state(id: UUID, payload: StateChangeRequest, session: AsyncSession = Depends(get_db)):
    logger.info("POST /incidents/{id}/state", extra={"work_item_id": str(id), "action": payload.action})

    if payload.action == "INVESTIGATING":
        wi = await workflow_service.transition_to_investigating(session, id)
    elif payload.action == "RESOLVED":
        wi = await workflow_service.transition_to_resolved(session, id)
    else:
        wi = await workflow_service.transition_to_closed(session, id)

    # Invalidate caches after state change
    await cache_service.invalidate_dashboard_cache()
    await cache_service.invalidate_incident_cache(str(id))
    return {"id": str(wi.id), "status": wi.status.value}

