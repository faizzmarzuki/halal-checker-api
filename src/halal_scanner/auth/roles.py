"""Role assignment and the admin-only access dependency."""
from __future__ import annotations

import os

from fastapi import Depends, HTTPException

from .dependencies import get_current_user
from .models import User


def _admin_emails() -> set[str]:
    """Parse HALAL_ADMIN_EMAILS (comma-separated) live on each call."""
    raw = os.environ.get("HALAL_ADMIN_EMAILS", "")
    return {e.strip() for e in raw.split(",") if e.strip()}


def resolve_role(email: str) -> str:
    """admin if the email is allow-listed, else user."""
    return "admin" if email in _admin_emails() else "user"


def is_admin(user: User) -> bool:
    return user.role == "admin"


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency: pass through admins, else 403."""
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    return user
