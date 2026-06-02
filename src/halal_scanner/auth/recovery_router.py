"""Account-recovery routes (no JWT — these are pre-auth recovery flows)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from . import recovery
from .account_tokens import AccountTokenError
from .recovery_schemas import EmailRequest, ResetConfirm, TokenConfirm

router = APIRouter(prefix="/auth", tags=["recovery"])


@router.post("/verify/request")
def verify_request(req: EmailRequest, db: Session = Depends(get_db)) -> dict:
    recovery.request_verification(db, req.email)
    return {"status": "ok"}


@router.post("/verify/confirm", status_code=204)
def verify_confirm(req: TokenConfirm, db: Session = Depends(get_db)) -> None:
    try:
        recovery.confirm_verification(db, req.token)
    except AccountTokenError:
        raise HTTPException(status_code=400, detail="Invalid or expired token.")


@router.post("/password-reset/request")
def reset_request(req: EmailRequest, db: Session = Depends(get_db)) -> dict:
    recovery.request_reset(db, req.email)
    return {"status": "ok"}


@router.post("/password-reset/confirm", status_code=204)
def reset_confirm(req: ResetConfirm, db: Session = Depends(get_db)) -> None:
    try:
        recovery.confirm_reset(db, req.token, req.new_password)
    except AccountTokenError:
        raise HTTPException(status_code=400, detail="Invalid or expired token.")
