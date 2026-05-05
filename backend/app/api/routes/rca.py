from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.rca import RCAResponse, RCASubmit
from app.services import cache_service
from app.services.rca_service import create_or_update_rca, get_rca


router = APIRouter(prefix="/incidents", tags=["rca"])


@router.post("/{id}/rca", response_model=RCAResponse)
async def submit_rca(id: UUID, payload: RCASubmit, session: AsyncSession = Depends(get_db)) -> RCAResponse:
    rca = await create_or_update_rca(session, id, payload)
    # RCA affects close eligibility and detail view.
    await cache_service.invalidate_incident_cache(str(id))
    await cache_service.invalidate_dashboard_cache()
    return RCAResponse.model_validate(rca)


@router.get("/{id}/rca", response_model=RCAResponse)
async def fetch_rca(id: UUID, session: AsyncSession = Depends(get_db)) -> RCAResponse:
    rca = await get_rca(session, id)
    if rca is None:
        # Let API return 404 for missing RCA
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RCA not found")
    return RCAResponse.model_validate(rca)

