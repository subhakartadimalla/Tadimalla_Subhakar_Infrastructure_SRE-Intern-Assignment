from __future__ import annotations

from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.rca import router as rca_router
from app.api.routes.test_cache import router as test_cache_router
from app.api.incidents import router as incidents_router
from app.api.signal import router as signal_router


api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(test_cache_router, tags=["test"])
api_router.include_router(signal_router, tags=["signals"])
api_router.include_router(rca_router)
api_router.include_router(incidents_router)

