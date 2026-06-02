"""Pydantic models for the /keys endpoints."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(default="", max_length=100)


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    prefix: str
    revoked: bool
    created_at: datetime


class ApiKeyCreated(ApiKeyOut):
    # The raw key, returned exactly once at creation.
    api_key: str
