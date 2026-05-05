from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.logging import configure_logging, get_logger
from app.core.redis import close_redis, init_redis
from app.core.settings import settings
from app.core.database import close_engine, init_engine
from app.core.metrics import metrics_loop


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level, service="ims-backend")
    logger.info("Starting IMS backend", extra={"env": settings.env})
    await init_engine(settings.database_url)
    await init_redis(settings.redis_url)
    metrics_task: asyncio.Task[None] | None = None
    try:
        metrics_task = asyncio.create_task(metrics_loop(settings.metrics_print_interval_seconds))
        yield
    finally:
        if metrics_task is not None:
            metrics_task.cancel()
        logger.info("Shutting down IMS backend")
        await close_redis()
        await close_engine()


app = FastAPI(title="Incident Management System (IMS)", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000.0
    logger.info(
        "HTTP request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
        },
    )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception", extra={"path": request.url.path, "method": request.method})
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


app.include_router(api_router)

