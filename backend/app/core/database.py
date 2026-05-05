from __future__ import annotations

import uuid
from datetime import datetime
from typing import AsyncIterator

from sqlalchemy import DateTime, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.logging import get_logger


logger = get_logger(__name__)

_engine: AsyncEngine | None = None
SessionLocal: async_sessionmaker[AsyncSession] | None = None


class Base(DeclarativeBase):
    """Declarative base for all models."""


class BaseModel(Base):
    """Base model with common, production-friendly fields."""

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )


async def init_engine(database_url: str) -> None:
    global _engine, SessionLocal
    if _engine is not None:
        return

    logger.info("Initializing async DB engine", extra={"database_url": database_url})
    _engine = create_engine(database_url)
    SessionLocal = async_sessionmaker(_engine, expire_on_commit=False, autoflush=False)
    try:
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Postgres connection OK")
    except Exception:
        logger.exception("Postgres connection FAILED", extra={"database_url": database_url})
        raise


async def close_engine() -> None:
    global _engine, SessionLocal
    if _engine is not None:
        logger.info("Disposing async DB engine")
        await _engine.dispose()
    _engine = None
    SessionLocal = None


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Database engine not initialized")
    return _engine


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields an async SQLAlchemy session."""
    if SessionLocal is None:
        raise RuntimeError("Session factory not initialized")
    async with SessionLocal() as session:
        yield session

