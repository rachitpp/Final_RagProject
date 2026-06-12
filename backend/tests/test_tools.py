"""The deterministic calculators — pure functions of their inputs, so they get
plain unit tests. These are the 'code does math' half of the system's core
doctrine; no policy data appears here, only caller-supplied figures."""
from llm.tools import compute_entitlement, compute_leave_ledger


# -------------------------------------------------------- compute_entitlement

def test_entitlement_sums_components_and_grand_total():
    # The exact failure class the tool exists for: 4000*3 + 2500*3 = 19500
    # (observed miscomputed as 21000 by the bare model — see llm/tools.py).
    out = compute_entitlement.invoke({
        "line_items": [
            {"band": "9/10", "component": "Lodging", "daily_rate": 4000, "days": 3},
            {"band": "9/10", "component": "Boarding", "daily_rate": 2500, "days": 3},
        ]
    })
    assert out == {
        "9/10": {"Lodging": 12000, "Boarding": 7500, "grand_total": 19500}
    }


def test_entitlement_multi_band_multi_leg():
    out = compute_entitlement.invoke({
        "line_items": [
            # Band 9/10: 2 legs of Lodging (different cities/rates) + Boarding.
            {"band": "9/10", "component": "Lodging", "daily_rate": 4000, "days": 3},
            {"band": "9/10", "component": "Lodging", "daily_rate": 2500, "days": 2},
            {"band": "9/10", "component": "Boarding", "daily_rate": 1500, "days": 5},
            {"band": "6-8", "component": "Lodging", "daily_rate": 3000, "days": 5},
        ]
    })
    assert out["9/10"]["Lodging"] == 4000 * 3 + 2500 * 2
    assert out["9/10"]["grand_total"] == 17000 + 1500 * 5
    assert out["6-8"] == {"Lodging": 15000, "grand_total": 15000}


def test_entitlement_applies_percent_of_rate_in_code():
    # The Singapore regression: 12 days at $200 with lodging provided (50%)
    # must be 1200, computed by the tool from the FULL rate + percentage —
    # the model passing a pre-multiplied (and once, wrong) rate is exactly
    # what this field eliminates.
    out = compute_entitlement.invoke({
        "line_items": [
            {"band": "9 & 10", "component": "DA", "daily_rate": 200,
             "days": 12, "percent_of_rate": 50},
        ]
    })
    assert out == {"9 & 10": {"DA": 1200, "grand_total": 1200}}


def test_entitlement_accepts_fractional_days():
    # Domestic timing rules produce half days (e.g. a partial period counting
    # as 0.5 day); the schema must not reject them — observed live as a
    # pydantic int_from_float error that made the model apologise and give up.
    out = compute_entitlement.invoke({
        "line_items": [
            {"band": "9/10", "component": "Boarding", "daily_rate": 750, "days": 1},
            {"band": "9/10", "component": "Boarding", "daily_rate": 750, "days": 0.5},
        ]
    })
    assert out["9/10"]["Boarding"] == 1125


def test_entitlement_percent_defaults_to_full_rate():
    out = compute_entitlement.invoke({
        "line_items": [
            {"band": "result", "component": "DA", "daily_rate": 200, "days": 3},
        ]
    })
    assert out["result"]["DA"] == 600


def test_entitlement_renders_whole_numbers_without_trailing_point():
    out = compute_entitlement.invoke({
        "line_items": [
            {"band": "result", "component": "DA", "daily_rate": 175.0, "days": 2},
        ]
    })
    assert out["result"]["DA"] == 350
    assert isinstance(out["result"]["DA"], int)


# ------------------------------------------------------- compute_leave_ledger

_PL = {
    "name": "PL",
    "eligibility_months": 0,
    "accrual_per_month": 1.5,
    "exclude_weekend_holiday": True,
}
_SL = {
    "name": "SL",
    "eligibility_months": 3,
    "annual_days": 7,
    "exclude_weekend_holiday": True,
}


def test_ledger_weekend_and_holiday_days_not_deducted():
    out = compute_leave_ledger.invoke({
        "join_date": "2024-01-01",
        "leave_types": [_PL],
        "holidays": ["2025-06-13"],  # Friday
        "leave_days": [
            {"date": "2025-06-12", "type": "PL"},  # Thursday -> deducted
            {"date": "2025-06-13", "type": "PL"},  # holiday  -> free
            {"date": "2025-06-14", "type": "PL"},  # Saturday -> free
        ],
    })
    assert out["deducted"] == {"PL": 1.0}
    assert out["not_deducted_weekly_offs_or_holidays"] == 2.0
    assert out["lwop_days"] == 0


def test_ledger_pre_eligibility_routes_to_lwop_with_violation():
    out = compute_leave_ledger.invoke({
        "join_date": "2025-06-01",
        "leave_types": [_SL],
        "leave_days": [{"date": "2025-07-01", "type": "SL"}],  # Tuesday, month 1
    })
    assert out["lwop_days"] == 1.0
    assert len(out["violations"]) == 1
    assert "2025-09-01" in out["violations"][0]["reason"]  # eligible from join+3mo
    assert out["deducted"] == {}


def test_ledger_balance_overflow_routes_to_lwop():
    # Joined 2025-01-01; by 2025-03-03 two whole months are complete -> 3.0 PL
    # accrued. Mon-Thu 03..06 requests 4 days: 3 deducted, the 4th overflows.
    out = compute_leave_ledger.invoke({
        "join_date": "2025-01-01",
        "leave_types": [_PL],
        "leave_days": [
            {"date": "2025-03-03", "type": "PL"},
            {"date": "2025-03-04", "type": "PL"},
            {"date": "2025-03-05", "type": "PL"},
            {"date": "2025-03-06", "type": "PL"},
        ],
    })
    assert out["deducted"] == {"PL": 3.0}
    assert out["lwop_days"] == 1.0
    assert out["balances"]["PL"]["remaining"] == 0.0


def test_ledger_accrual_cap_is_respected():
    capped = dict(_PL, cap=2.0)
    out = compute_leave_ledger.invoke({
        "join_date": "2024-01-01",  # years of accrual, but capped at 2
        "leave_types": [capped],
        "leave_days": [
            {"date": "2025-06-10", "type": "PL"},  # Tue
            {"date": "2025-06-11", "type": "PL"},  # Wed
            {"date": "2025-06-12", "type": "PL"},  # Thu -> beyond cap -> LWOP
        ],
    })
    assert out["deducted"] == {"PL": 2.0}
    assert out["lwop_days"] == 1.0


def test_ledger_balance_query_from_already_taken_record():
    # The "how many CL/PL do I have left?" path: no scenario days, the HR
    # record seeds the balance, as_of fixes the accrual date. CL is credited
    # upfront (7/yr), PL accrues 1.5/mo capped at 30.
    out = compute_leave_ledger.invoke({
        "join_date": "2019-03-11",
        "leave_days": [],
        "leave_types": [
            {"name": "CL", "annual_days": 7, "credit_upfront": True},
            dict(_PL, cap=30),
        ],
        "already_taken": {"CL": 3, "PL": 6},
        "as_of": "2026-06-12",
    })
    assert out["balances"]["CL"]["remaining"] == 4.0   # 7 credited - 3 taken
    assert out["balances"]["PL"]["remaining"] == 24.0  # cap 30 - 6 taken
    assert out["balances"]["CL"]["as_of"] == "2026-06-12"
    assert out["deducted"] == {}  # nothing new was planned
    # The basis echo mirrors the exact inputs used (the model's self-check).
    assert out["balances"]["PL"]["basis"]["cap"] == 30
    assert out["balances"]["PL"]["basis"]["already_taken"] == 6.0
    assert out["balances"]["PL"]["basis"]["join_date"] == "2019-03-11"


def test_ledger_balance_without_as_of_defaults_to_today():
    # A balance query that forgets as_of must not report zero accrual as of
    # the join date — it reports as of today.
    from datetime import date as _date
    out = compute_leave_ledger.invoke({
        "join_date": "2019-03-11",
        "leave_days": [],
        "leave_types": [{"name": "SL", "annual_days": 7, "cap": 14}],
        "already_taken": {"SL": 2},
    })
    assert out["balances"]["SL"]["as_of"] == _date.today().isoformat()
    assert out["balances"]["SL"]["remaining"] == 12.0  # min(accrued, 14) - 2


def test_ledger_scenario_balance_starts_from_already_taken():
    # 7 CL/yr with 5 already taken: a Mon-Wed 3-day plan deducts the 2 that
    # remain and overflows the 3rd to LWOP.
    out = compute_leave_ledger.invoke({
        "join_date": "2020-01-01",
        "leave_days": [
            {"date": "2026-06-08", "type": "CL"},
            {"date": "2026-06-09", "type": "CL"},
            {"date": "2026-06-10", "type": "CL"},
        ],
        "leave_types": [{"name": "CL", "annual_days": 7, "credit_upfront": True}],
        "already_taken": {"CL": 5},
    })
    assert out["deducted"] == {"CL": 2.0}
    assert out["lwop_days"] == 1.0
    assert out["balances"]["CL"]["remaining"] == 0.0
