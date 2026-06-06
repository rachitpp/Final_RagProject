"""Roster importer: upsert preserves auth fields; validation rejects bad input."""
import pandas as pd
import pytest

from api.security import hash_password
from db.models import User
from db.session import SessionLocal
from import_employees import RosterValidationError, import_employees

GOOD_ROW = {
    "Employee ID": "E900",
    "Employee Name": "Test Person",
    "Email": "test@company.com",
    "Band": 7,
    "Date of Joining": "2020-01-01",
}


def _write_roster(path, rows):
    pd.DataFrame(rows).to_excel(path, index=False)
    return str(path)


def test_import_inserts_then_upserts_preserving_password(tmp_path):
    xlsx = _write_roster(tmp_path / "roster.xlsx", [GOOD_ROW])
    assert import_employees(xlsx) == (1, 0)  # inserted

    # Simulate the employee activating (sets a password hash).
    with SessionLocal() as db:
        db.get(User, "E900").password_hash = hash_password("secret")
        db.commit()

    # Re-importing the same roster refreshes roster fields but MUST NOT wipe auth.
    assert import_employees(xlsx) == (0, 1)  # updated
    with SessionLocal() as db:
        assert db.get(User, "E900").password_hash is not None


def test_import_lowercases_email(tmp_path):
    xlsx = _write_roster(tmp_path / "roster.xlsx", [{**GOOD_ROW, "Email": "MixedCase@Company.com"}])
    import_employees(xlsx)
    with SessionLocal() as db:
        assert db.get(User, "E900").email == "mixedcase@company.com"


def test_import_rejects_letter_band(tmp_path):
    xlsx = _write_roster(tmp_path / "roster.xlsx", [{**GOOD_ROW, "Band": "A"}])
    with pytest.raises(RosterValidationError):
        import_employees(xlsx)


def test_import_rejects_out_of_range_band(tmp_path):
    xlsx = _write_roster(tmp_path / "roster.xlsx", [{**GOOD_ROW, "Band": 11}])
    with pytest.raises(RosterValidationError):
        import_employees(xlsx)


def test_import_rejects_duplicate_employee_id(tmp_path):
    rows = [GOOD_ROW, {**GOOD_ROW, "Email": "other@company.com"}]
    xlsx = _write_roster(tmp_path / "roster.xlsx", rows)
    with pytest.raises(RosterValidationError):
        import_employees(xlsx)


def test_import_rejects_missing_column(tmp_path):
    row = {k: v for k, v in GOOD_ROW.items() if k != "Email"}
    xlsx = _write_roster(tmp_path / "roster.xlsx", [row])
    with pytest.raises(RosterValidationError):
        import_employees(xlsx)
