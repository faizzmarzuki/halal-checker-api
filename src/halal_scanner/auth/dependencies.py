"""FastAPI dependency that resolves the current user from a Bearer token."""
from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from . import tokens
from .models import User

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    try:
        payload = tokens.decode_token(creds.credentials, "access")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token.") from exc
    user = db.scalar(select(User).where(User.id == int(payload["sub"])))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive.")
    return user
