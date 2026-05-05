from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel
from app.models.enums import SeverityLevel, WorkItemStatus


class WorkItem(BaseModel):
    __tablename__ = "work_items"

    component_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    severity: Mapped[SeverityLevel] = mapped_column(
        Enum(SeverityLevel, name="severity_level"), nullable=False, index=True
    )
    status: Mapped[WorkItemStatus] = mapped_column(
        Enum(WorkItemStatus, name="work_item_status"), nullable=False, index=True, default=WorkItemStatus.OPEN
    )

    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    first_signal_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_signal_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    signal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    rca: Mapped["RCA | None"] = relationship(
        back_populates="work_item",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        # Composite index for component-focused timeline queries.
        Index("ix_work_items_component_id_created_at", "component_id", "created_at"),
        Index("ix_work_items_status", "status"),
        Index("ix_work_items_severity", "severity"),
    )

