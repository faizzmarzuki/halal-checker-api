"""HTTP routes for API key management, mounted at /keys (JWT required)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from . import keys as keys_service
from .dependencies import get_current_user
from .keys_schemas import ApiKeyCreate, ApiKeyCreated, ApiKeyOut
from .models import ApiKey, User

router = APIRouter(prefix="/keys", tags=["api-keys"])


@router.post("", response_model=ApiKeyCreated, status_code=201)
def create_key(
    req: ApiKeyCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiKeyCreated:
    row, raw = keys_service.create_key(db, user, req.name)
    return ApiKeyCreated(
        id=row.id,
        name=row.name,
        prefix=row.prefix,
        revoked=row.revoked,
        created_at=row.created_at,
        api_key=raw,
    )


@router.get("", response_model=list[ApiKeyOut])
def list_keys(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ApiKey]:
    return keys_service.list_keys(db, user)


@router.delete("/{key_id}", status_code=204)
def delete_key(
    key_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        keys_service.revoke_key(db, user, key_id)
    except keys_service.KeyNotFound:
        raise HTTPException(status_code=404, detail="API key not found.")
