"""HTTP routes for a user's own scan history, mounted at /history (JWT required)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import history
from ..auth.dependencies import get_current_user
from ..auth.models import User
from ..db import get_db
from .schemas import ScanHistoryOut

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=list[ScanHistoryOut])
def list_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list:
    return history.list_for_user(db, user, limit=limit, offset=offset)


@router.delete("/{scan_id}", status_code=204)
def delete_history_item(
    scan_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        history.delete_one(db, user, scan_id)
    except history.NotFound:
        raise HTTPException(status_code=404, detail="Scan not found.")


@router.delete("", status_code=204)
def clear_history(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    history.delete_all(db, user)
