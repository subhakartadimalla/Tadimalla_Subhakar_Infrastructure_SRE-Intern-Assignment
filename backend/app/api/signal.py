from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.core.logging import get_logger
from app.core.metrics import (
    inc_rejected_backpressure,
    inc_rejected_rate_limited,
    inc_rejected_redis_down,
    inc_signals_ingested,
)
from app.core.settings import settings
from app.schemas.signal import SignalAccepted, SignalIn
from app.services.queue_service import get_queue_length, is_rate_limited, push_signal


router = APIRouter()
logger = get_logger(__name__)


def _client_ip(request: Request) -> str:
    # Prefer X-Forwarded-For when behind proxy; otherwise use direct client.
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


@router.post("/signals", response_model=SignalAccepted)
async def ingest_signal(payload: SignalIn, request: Request) -> SignalAccepted:
    client_ip = _client_ip(request)

    # Rate limiting (mandatory). If Redis is down, fail fast with 503.
    try:
        limited = await is_rate_limited(client_ip, limit_per_sec=settings.ingest_rate_limit_per_sec)
    except RuntimeError:
        await inc_rejected_redis_down()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis unavailable")

    if limited:
        await inc_rejected_rate_limited()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    # Backpressure: reject when queue is too large.
    qlen = await get_queue_length()
    if qlen is not None and qlen >= settings.signal_queue_max_length:
        logger.warning(
            "Backpressure: queue overloaded",
            extra={"queue_length": qlen, "threshold": settings.signal_queue_max_length},
        )
        await inc_rejected_backpressure()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Queue overloaded")

    # Lightweight dict, no DB writes.
    signal_dict = {
        "component_id": payload.component_id,
        "timestamp": payload.timestamp.isoformat(),
        "severity": payload.severity.value,
        "message": payload.message,
        "metadata": payload.metadata or {},
        "client_ip": client_ip,
    }

    ok = await push_signal(signal_dict)
    if not ok:
        await inc_rejected_redis_down()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis unavailable")

    await inc_signals_ingested()
    return SignalAccepted(accepted=True)

