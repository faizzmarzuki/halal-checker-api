"""Pydantic request models for the account-recovery endpoints."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field

_FORBID = ConfigDict(extra="forbid")


class EmailRequest(BaseModel):
    model_config = _FORBID
    email: EmailStr


class TokenConfirm(BaseModel):
    model_config = _FORBID
    token: str = Field(min_length=1)


class ResetConfirm(BaseModel):
    model_config = _FORBID
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)
