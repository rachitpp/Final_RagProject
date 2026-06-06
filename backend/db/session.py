# =============================================================
# Engine + session wiring.
#
# - `engine`       : one process-wide SQLAlchemy engine bound to settings.database_url
# - `SessionLocal` : session factory; call it per-request/per-task
# - `get_db`       : FastAPI dependency yielding a session and closing it after
# - `init_db`      : create tables if missing (idempotent; never drops)
# =============================================================
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import settings
from db.base import Base

# SQLite + a threaded server (uvicorn/FastAPI) needs check_same_thread=False so a
# connection can be used across the worker threads. Harmless for other backends
# because the arg is only applied to SQLite URLs.
_is_sqlite = settings.database_url.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(settings.database_url, connect_args=_connect_args)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create all tables if they don't exist. Idempotent; never drops anything."""
    # Import models for their side effect: registering tables on Base.metadata.
    from db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yield a session, always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
