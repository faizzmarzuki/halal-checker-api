"""Admin-only routes (JWT + admin role), mounted at /admin."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from . import audit
from .admin_schemas import AuditEntryOut
from .models import User
from .roles import require_admin
from .schemas import UserOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
def list_users(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[User]:
    return list(db.scalars(select(User)))


@router.get("/audit", response_model=list[AuditEntryOut])
def list_audit(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list:
    return audit.list_recent(db)
