"""Shared test fixtures.

CRITICAL ordering: the DATABASE_URL and JWT_SECRET env vars are set HERE, at
import time, before any application module is imported. The `settings` singleton
is a frozen dataclass built on first import that reads these vars, and pytest
imports conftest.py before the test modules — so this runs first and every test
hits an isolated temp SQLite DB, never the real data/app.db.
"""
import os
import tempfile

_db_fd, _db_path = tempfile.mkstemp(suffix="-authtest.db")
os.close(_db_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-min-32-bytes-long")

import pytest

from api.ratelimit import chat_limiter, login_limiter
from db.base import Base
from db.models import User
from db.session import SessionLocal, engine


@pytest.fixture(autouse=True)
def fresh_db():
    """Rebuild the schema, reseed two un-activated users, and clear the rate
    limiters before every test, so tests are fully isolated and order-independent."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    login_limiter.reset()
    chat_limiter.reset()
    with SessionLocal() as db:
        db.add_all([
            User(employee_id="E101", name="Rahul", email="rahul@company.com", band=9),
            User(employee_id="E105", name="Kunal", email="kunal@company.com", band=10),
        ])
        db.commit()
    yield


def pytest_sessionfinish(session, exitstatus):
    """Remove the temp DB file after the run."""
    try:
        os.remove(_db_path)
    except OSError:
        pass
