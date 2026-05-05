from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RCASubmit(BaseModel):
    root_cause: str = Field(min_length=1)
    fix_applied: str = Field(min_length=1)
    prevention_steps: str = Field(min_length=1)
    start_time: datetime
    end_time: datetime


class RCAResponse(BaseModel):
    id: uuid.UUID
    work_item_id: uuid.UUID
    root_cause: str
    fix_applied: str
    prevention_steps: str
    start_time: datetime
    end_time: datetime
    mttr: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

