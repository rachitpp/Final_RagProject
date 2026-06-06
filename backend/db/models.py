# =============================================================
# ORM models.
#
# `User` is the roster row imported from the employee Excel sheet
# (import_employees.py) and the identity that auth issues JWTs for.
#
# Two distinct groups of columns:
#   - Roster fields (name, email, band, date_of_joining) — owned by the
#     Excel sheet; refreshed on every import via UPSERT.
#   - Auth fields (password_hash, activated_at) — owned by the app;
#     set at activation. The importer must NEVER overwrite these.
# =============================================================
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class User(Base):
    __tablename__ = "users"

    # --- Identity / roster (sourced from the Excel sheet) ---
    employee_id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "E101" — login key
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    # Numeric pay band 1–10; rate tables are keyed on this. Server-authoritative,
    # never typed by the user (see docs/AUTH_PERSONALIZATION_DESIGN.md).
    band: Mapped[int] = mapped_column(Integer, nullable=False)
    # Parked for leave accrual; nullable so older rosters without it still import.
    date_of_joining: Mapped[date | None] = mapped_column(Date, nullable=True)

    # --- Auth (owned by the app, set at activation — importer must not touch) ---
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    role: Mapped[str] = mapped_column(String, nullable=False, default="employee")

    # --- Bookkeeping ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    @property
    def is_activated(self) -> bool:
        """True once the user has set a password (first-time activation done)."""
        return self.password_hash is not None

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User {self.employee_id} band={self.band} activated={self.is_activated}>"
