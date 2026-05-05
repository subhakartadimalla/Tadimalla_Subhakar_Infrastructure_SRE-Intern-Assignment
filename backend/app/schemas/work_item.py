from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import SeverityLevel, WorkItemStatus


class WorkItemCreate(BaseModel):
    component_id: str = Field(min_length=1, max_length=128)
    severity: SeverityLevel
    title: str = Field(min_length=1, max_length=160)
    description: str | None = None
    first_signal_time: datetime
    last_signal_time: datetime
    signal_count: int = Field(default=1, ge=1)


class WorkItemResponse(BaseModel):
    id: uuid.UUID
    component_id: str
    severity: SeverityLevel
    status: WorkItemStatus
    title: str
    description: str | None
    first_signal_time: datetime
    last_signal_time: datetime
    signal_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

