from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import SeverityLevel


class SignalIn(BaseModel):
    component_id: str = Field(min_length=1, max_length=128)
    timestamp: datetime
    severity: SeverityLevel
    message: str = Field(min_length=1, max_length=256)
    metadata: dict[str, Any] | None = None


class SignalAccepted(BaseModel):
    accepted: bool

