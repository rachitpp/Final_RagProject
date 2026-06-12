# =============================================================
# Engine + session wiring.
#
# - `engine`       : one process-wide SQLAlchemy engine bound to settings.database_url
# - `SessionLocal` : session factory; call it per-request/per-task
# - `get_db`       : FastAPI dependency yielding a session and closing it after
# - `init_db`      : create tables if missing (idempotent; never drops)
# =============================================================
from typing import Generator

from sqlalchemy import create_engine, inspect, text
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
    _ensure_user_columns()


def _ensure_user_columns() -> None:
    """Minimal in-place migration (Alembic is consciously deferred — see
    docs/PROGRESS.md): create_all() only creates missing TABLES, so a DB file
    from before a model gained a column would crash every SELECT. ADD any
    users column listed here that the file lacks. Idempotent; never drops, so
    activated accounts (password_hash) survive schema growth."""
    insp = inspect(engine)
    if not insp.has_table("users"):
        return
    have = {c["name"] for c in insp.get_columns("users")}
    needed = {
        "pl_taken": "FLOAT NOT NULL DEFAULT 0",
        "sl_taken": "FLOAT NOT NULL DEFAULT 0",
        "cl_taken": "FLOAT NOT NULL DEFAULT 0",
    }
    with engine.begin() as conn:
        for name, ddl in needed.items():
            if name not in have:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {name} {ddl}"))


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yield a session, always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
