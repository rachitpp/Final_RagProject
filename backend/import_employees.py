# =============================================================
# One-time / repeatable roster import: Excel sheet -> users table.
#
#   cd backend && venv/bin/python import_employees.py
#
# Reads settings.employee_xlsx_path, validates it, and UPSERTs each row by
# employee_id. Roster fields (name, email, band, date_of_joining) are refreshed;
# the auth fields (password_hash, activated_at) are NEVER touched, so re-running
# after employees have activated will not wipe their passwords.
#
# Safe to run repeatedly. Creates the table if missing; never drops it.
# =============================================================
from __future__ import annotations

import sys
from datetime import date

import pandas as pd

from config.settings import settings
from db.models import User
from db.session import SessionLocal, init_db

# Excel header -> meaning. All five are required.
REQUIRED_COLUMNS = ["Employee ID", "Employee Name", "Email", "Band", "Date of Joining"]


class RosterValidationError(Exception):
    """Raised for any validation failure; aborts the import without writing."""


def _parse_date_of_joining(value) -> date | None:
    """Accept a YYYY-MM-DD string, a pandas/py datetime, or blank -> None."""
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
        return None
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        raise RosterValidationError(f"unparseable Date of Joining: {value!r}")
    return ts.date()


def _validate(df: pd.DataFrame) -> None:
    """Fail loudly before touching the DB."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise RosterValidationError(f"missing required column(s): {missing}")

    ids = df["Employee ID"].astype(str).str.strip()
    if ids.eq("").any():
        raise RosterValidationError("blank Employee ID in sheet")
    dupes = ids[ids.duplicated()].unique().tolist()
    if dupes:
        raise RosterValidationError(f"duplicate Employee ID(s): {dupes}")

    # Normalize to lowercase before the duplicate check so case-only variants
    # (Foo@x.com vs foo@x.com) are caught — emails are stored and matched
    # lowercased everywhere (see import loop and auth.activate).
    emails = df["Email"].astype(str).str.strip().str.lower()
    if emails.eq("").any():
        raise RosterValidationError("blank Email in sheet")
    email_dupes = emails[emails.duplicated()].unique().tolist()
    if email_dupes:
        raise RosterValidationError(f"duplicate Email(s): {email_dupes}")

    # Band must be a whole number 1–10 (NOT a letter grade).
    bands = pd.to_numeric(df["Band"], errors="coerce")
    bad = df["Band"][bands.isna() | (bands % 1 != 0) | (bands < 1) | (bands > 10)]
    if not bad.empty:
        raise RosterValidationError(
            f"Band must be an integer 1–10; offending values: {bad.tolist()}"
        )


def import_employees(xlsx_path: str | None = None) -> tuple[int, int]:
    """Import the roster. Returns (inserted, updated) counts."""
    path = xlsx_path or settings.employee_xlsx_path
    df = pd.read_excel(path)
    _validate(df)

    init_db()  # create users table if it doesn't exist yet

    inserted = updated = 0
    with SessionLocal() as db:
        for _, row in df.iterrows():
            emp_id = str(row["Employee ID"]).strip()
            name = str(row["Employee Name"]).strip()
            email = str(row["Email"]).strip().lower()
            band = int(pd.to_numeric(row["Band"]))
            doj = _parse_date_of_joining(row["Date of Joining"])

            user = db.get(User, emp_id)
            if user is None:
                # New roster row — password_hash/activated_at stay NULL until activation.
                db.add(User(
                    employee_id=emp_id, name=name, email=email,
                    band=band, date_of_joining=doj,
                ))
                inserted += 1
            else:
                # UPSERT: refresh roster fields only. Auth fields are left alone.
                user.name = name
                user.email = email
                user.band = band
                user.date_of_joining = doj
                updated += 1

        db.commit()

    return inserted, updated


def main() -> int:
    try:
        inserted, updated = import_employees()
    except FileNotFoundError:
        print(f"ERROR: roster not found at {settings.employee_xlsx_path}", file=sys.stderr)
        return 1
    except RosterValidationError as e:
        print(f"ERROR: invalid roster — {e}", file=sys.stderr)
        return 1
    print(f"Roster import OK: {inserted} inserted, {updated} updated "
          f"({inserted + updated} rows).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
