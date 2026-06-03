"""SQLAlchemy engine, session factory, and Base for the accounts system.

The connection string comes from HALAL_DATABASE_URL (default: local SQLite
file) so it can be pointed at PostgreSQL later without code changes.
"""
from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _normalize_db_url(url: str) -> str:
    """Adapt common Postgres URL schemes to the installed psycopg3 driver.

    Render gives ``postgresql://…`` and Heroku-style ``postgres://…`` is common;
    SQLAlchemy would otherwise default to the (uninstalled) psycopg2 driver. A
    URL that already names a driver (``postgresql+psycopg://`` /
    ``postgresql+psycopg2://``) or any non-Postgres URL (SQLite) is returned
    unchanged.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _make_engine():
    url = _normalize_db_url(
        os.environ.get("HALAL_DATABASE_URL", "sqlite:///./halal_scanner.db")
    )
    # check_same_thread=False lets the SQLite connection be shared across
    # FastAPI's threadpool workers; harmless for other backends (skipped).
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yield a session and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
