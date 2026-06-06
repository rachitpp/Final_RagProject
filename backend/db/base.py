# =============================================================
# Declarative base shared by every ORM model.
# Kept in its own module so models.py and session.py can both
# import it without a circular dependency.
# =============================================================
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models (SQLAlchemy 2.0 typed style)."""
    pass
