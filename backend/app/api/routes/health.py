from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import text

from app.core.logging import get_logger
from app.core.database import get_engine
from app.core.redis import get_redis


router = APIRouter()
logger = get_logger(__name__)


@router.get("/health")
async def health() -> dict[str, object]:
    services: dict[str, str] = {}
    database_ok = False
    redis_ok = False

    # Verify DB connectivity
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        services["database"] = "connected"
        database_ok = True
    except Exception:
        services["database"] = "down"
        logger.exception("Healthcheck failed: database")

    # Verify Redis connectivity
    try:
        redis = get_redis()
        await redis.ping()
        services["redis"] = "connected"
        redis_ok = True
    except Exception:
        services["redis"] = "down"
        logger.exception("Healthcheck failed: redis")

    if database_ok and redis_ok:
        status = "ok"
    elif database_ok or redis_ok:
        status = "degraded"
        logger.critical("Healthcheck degraded", extra={"services": services})
    else:
        status = "down"
        logger.critical("Healthcheck down", extra={"services": services})

    return {
        "status": status,
        "services": services,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

