"""HTTP routes for accounts, mounted at /auth."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from . import service
from .dependencies import get_current_user
from .models import User
from .schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)) -> User:
    try:
        return service.register(db, req.email, req.password)
    except service.EmailTaken:
        raise HTTPException(status_code=409, detail="Email already registered.")


@router.post("/login", response_model=TokenPair)
def login(req: LoginRequest, db: Session = Depends(get_db)) -> TokenPair:
    try:
        user = service.authenticate(db, req.email, req.password)
    except service.InvalidCredentials:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    access, refresh = service.issue_tokens(db, user)
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenPair)
def refresh(req: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    try:
        access, refresh_token = service.rotate_refresh(db, req.refresh_token)
    except service.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid refresh token.")
    return TokenPair(access_token=access, refresh_token=refresh_token)


@router.post("/logout", status_code=204)
def logout(req: RefreshRequest, db: Session = Depends(get_db)) -> None:
    try:
        service.logout(db, req.refresh_token)
    except service.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid refresh token.")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
