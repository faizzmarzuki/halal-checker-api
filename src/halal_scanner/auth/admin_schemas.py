"""Pydantic response model for audit entries."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    action: str
    user_id: int | None
    detail: str
    created_at: datetime
