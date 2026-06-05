"""
Deterministic calculation tool the answer LLM can call.

Why this exists: LLMs are unreliable at multi-step arithmetic — they read the
right per-day rates from the policy but slip when multiplying by days and
summing across legs (we observed ₹4000×3 + ₹2500×3 come back as 21000 instead
of 19500). The industry fix is "code does math, the model does language": the
model extracts the figures FROM THE CONTEXT and calls this tool, which computes
the totals exactly. No policy data lives here — every rate is supplied by the
caller, read from the retrieved policy tables, so the PDF stays the source of
truth.
"""
import calendar as _calendar
from datetime import date, datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from utils.logger import get_logger

logger = get_logger(__name__)


class LineItem(BaseModel):
    """One (band, component, leg) entitlement line to be totalled."""
    band: str = Field(
        description="Band group label exactly as the policy lists it, e.g. "
        "'9/10'. If the question fixes a single band or band is irrelevant, "
        "use 'result'."
    )
    component: str = Field(
        description="Allowance component name as the policy names it, e.g. "
        "'Lodging', 'Boarding', 'DA'."
    )
    daily_rate: float = Field(
        description="The per-day amount for this component on this leg, read "
        "from the policy table in the context. Number only — no currency symbol."
    )
    days: int = Field(
        description="Number of days this rate applies for this leg."
    )


def _num(n: float) -> float:
    """Drop the trailing .0 on whole numbers so totals render as 24750, not 24750.0."""
    f = float(n)
    return int(f) if f.is_integer() else round(f, 2)


@tool
def compute_entitlement(line_items: List[LineItem]) -> dict:
    """Compute exact travel-reimbursement subtotals and grand totals.

    Call this for EVERY question that needs a daily rate multiplied by days or
    summed across legs/components — do NOT do that arithmetic yourself. Read each
    daily_rate from the policy tables in the context and pass one line item per
    (band, component, leg). Returns, per band: each component's subtotal (the
    rate×days summed across all legs) and the grand total (sum of the component
    subtotals). Use the returned numbers verbatim in your answer.
    """
    result: dict[str, dict[str, float]] = {}
    for item in line_items:
        # LangChain may hand us LineItem instances or plain dicts.
        band = (item.band if hasattr(item, "band") else item["band"]) or "result"
        component = item.component if hasattr(item, "component") else item["component"]
        rate = float(item.daily_rate if hasattr(item, "daily_rate") else item["daily_rate"])
        days = int(item.days if hasattr(item, "days") else item["days"])
        bucket = result.setdefault(str(band), {})
        bucket[str(component)] = bucket.get(str(component), 0.0) + rate * days

    out: dict[str, dict[str, float]] = {}
    for band, comps in result.items():
        grand = sum(comps.values())
        out[band] = {c: _num(v) for c, v in comps.items()}
        out[band]["grand_total"] = _num(grand)
    logger.info(f"compute_entitlement -> {out}")
    return out


# ===========================================================================
# Leave ledger — the leave-side equivalent of compute_entitlement.
#
# Why this exists: leave answers need multi-step date + balance + eligibility
# logic (service-months vs a cutoff, pro-rata accrual, weekend/holiday
# exclusion, running balance, overflow -> LWOP). LLMs recite these rules but
# don't enforce them — so the math lives here. No policy data is hardcoded:
# every rate, cutoff, cap and holiday is supplied by the caller, read from the
# retrieved leave policy. Code does the calendar/ledger; the model reads rules.
# ===========================================================================

_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday",
             "Friday", "Saturday", "Sunday"]


def _parse_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def _months_completed(start: date, end: date) -> int:
    """Whole calendar months from start to end (e.g. Mar 15 -> Jun 15 = 3)."""
    if end < start:
        return 0
    m = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        m -= 1
    return max(0, m)


def _add_months(d: date, n: int) -> date:
    total = (d.month - 1) + n
    y = d.year + total // 12
    m = total % 12 + 1
    return date(y, m, min(d.day, _calendar.monthrange(y, m)[1]))


class LeaveTypeRule(BaseModel):
    """One leave type's rules, read from the policy context."""
    name: str = Field(description="Leave type name as the policy names it, e.g. 'PL', 'SL', 'CL'.")
    eligibility_months: int = Field(0, description="Months of continuous service required before the FIRST availment of this type (0 if none).")
    accrual_per_month: Optional[float] = Field(None, description="Days accrued per completed calendar month worked (e.g. PL 1.5). Use this OR annual_days.")
    annual_days: Optional[float] = Field(None, description="Days granted per year (e.g. SL/CL 7), accrued pro-rata over the year unless credit_upfront.")
    credit_upfront: bool = Field(False, description="True if the whole pro-rata annual amount is credited at once and available immediately (e.g. CL).")
    exclude_weekend_holiday: bool = Field(True, description="True if weekly-offs/holidays within this leave are NOT counted (PL, SL); False if they ARE (LWOP).")
    cap: Optional[float] = Field(None, description="Maximum accumulation cap for this type, if the policy sets one (e.g. PL 30, SL 14).")
    combinable_with: List[str] = Field(default_factory=list, description="Leave types this type may be prefixed/suffixed with in one continuous stretch (e.g. PL -> ['SL','LWOP']). Types NOT listed may not be combined with it (e.g. CL -> []).")


class LeaveDay(BaseModel):
    """One day of intended absence and the leave type planned for it."""
    date: str = Field(description="Calendar date of one day of intended absence, ISO 'YYYY-MM-DD'.")
    type: str = Field(description="Leave type planned for this day (must match a LeaveTypeRule.name).")
    fraction: float = Field(1.0, description="Portion of the day taken (1.0 full, 0.5 half).")


@tool
def compute_leave_ledger(
    join_date: str,
    leave_days: List[LeaveDay],
    leave_types: List[LeaveTypeRule],
    holidays: Optional[List[str]] = None,
    weekend_days: Optional[List[str]] = None,
) -> dict:
    """Deterministically resolve a leave scenario: per-day outcome, deductions
    per type, eligibility violations, and Leave-Without-Pay (LWOP) overflow.

    Call this for EVERY leave question that involves dates, a join date, multiple
    leave types, accrual, balances or eligibility — do NOT do that date
    arithmetic, accrual, balance tracking or eligibility checking yourself. Read
    every RULE (accrual rates, eligibility months, caps, which types exclude
    weekends/holidays) and the holiday dates from the policy context, enumerate
    the intended leave days with their types, and pass them in. Use the returned
    `deducted`, `lwop_days`, `violations` and `per_day` verbatim.

    Logic: a day that is a weekend or holiday is NOT deducted for types with
    exclude_weekend_holiday=True. A day before (join_date + eligibility_months)
    for its type is a violation and routes to LWOP. Accrual is computed to each
    day's date (accrual_per_month * completed months, or annual_days pro-rata by
    months/12, or the full pro-rata amount if credit_upfront, capped at `cap`);
    a request beyond the available balance overflows to LWOP.
    """
    join = _parse_date(join_date)
    holiset = {_parse_date(h) for h in (holidays or [])}
    weekend = {w.strip().lower() for w in (weekend_days or ["Saturday", "Sunday"])}
    rules = {r.name: r for r in leave_types}

    used: dict[str, float] = {r.name: 0.0 for r in leave_types}
    deducted: dict[str, float] = {r.name: 0.0 for r in leave_types}
    lwop = 0.0
    offs = 0.0
    violations: list[dict] = []
    per_day: list[dict] = []

    def accrued_to(rule: LeaveTypeRule, on: date) -> float:
        months = _months_completed(join, on)
        if rule.accrual_per_month is not None:
            acc = rule.accrual_per_month * months
        elif rule.annual_days is not None:
            if rule.credit_upfront:
                acc = (rule.annual_days * (12 - join.month + 1) / 12
                       if on.year == join.year else rule.annual_days)
            else:
                acc = rule.annual_days * months / 12
        else:
            acc = 0.0
        return min(acc, rule.cap) if rule.cap is not None else acc

    for ld in sorted(leave_days, key=lambda x: x.date):
        d = _parse_date(ld.date)
        wd = _WEEKDAYS[d.weekday()]
        rule = rules.get(ld.type)
        frac = ld.fraction
        if rule is None:
            per_day.append({"date": ld.date, "weekday": wd, "requested": ld.type,
                            "outcome": f"unknown leave type {ld.type!r}"})
            continue
        if (wd.lower() in weekend or d in holiset) and rule.exclude_weekend_holiday:
            offs += frac
            per_day.append({"date": ld.date, "weekday": wd, "requested": ld.type,
                            "outcome": "not deducted (weekly off / holiday)"})
            continue
        elig_from = _add_months(join, rule.eligibility_months) if rule.eligibility_months else join
        if d < elig_from:
            lwop += frac
            violations.append({"date": ld.date, "type": ld.type,
                               "reason": f"before first-availment eligibility (eligible from {elig_from.isoformat()})"})
            per_day.append({"date": ld.date, "weekday": wd, "requested": ld.type,
                            "outcome": f"LWOP — {ld.type} not eligible until {elig_from.isoformat()}"})
            continue
        available = accrued_to(rule, d) - used[ld.type]
        if available >= frac:
            used[ld.type] += frac
            deducted[ld.type] += frac
            per_day.append({"date": ld.date, "weekday": wd, "requested": ld.type,
                            "outcome": f"deducted {frac} {ld.type}"})
        else:
            lwop += frac
            per_day.append({"date": ld.date, "weekday": wd, "requested": ld.type,
                            "outcome": f"LWOP — {ld.type} balance exhausted (~{max(available, 0):.2f} left)"})

    # Combination rules: within a continuous stretch (consecutive days, only
    # weekends/holidays allowed between), flag any leave-type adjacency the policy
    # does not permit (e.g. CL prefixed/suffixed with SL/PL).
    def _only_offs_between(d1: date, d2: date) -> bool:
        cur = d1 + timedelta(days=1)
        while cur < d2:
            if not (_WEEKDAYS[cur.weekday()].lower() in weekend or cur in holiset):
                return False
            cur += timedelta(days=1)
        return True

    planned = [(pd["requested"], pd["date"]) for pd in per_day
               if "not deducted" not in pd["outcome"]]
    combination_violations: list[dict] = []
    for (a, da), (b, db) in zip(planned, planned[1:]):
        if a == b or not _only_offs_between(_parse_date(da), _parse_date(db)):
            continue
        ra, rb = rules.get(a), rules.get(b)
        ok = (rb is not None and a in rb.combinable_with) or \
             (ra is not None and b in ra.combinable_with)
        if not ok:
            combination_violations.append({
                "between": [da, db], "types": [a, b],
                "reason": f"{a} may not be prefixed/suffixed with {b} per policy",
            })

    as_of = max((_parse_date(ld.date) for ld in leave_days), default=join)
    balances = {
        r.name: {
            "accrued": round(accrued_to(r, as_of), 2),
            "used": round(used[r.name], 2),
            "remaining": round(accrued_to(r, as_of) - used[r.name], 2),
            "as_of": as_of.isoformat(),
        }
        for r in leave_types
    }

    out = {
        "deducted": {k: round(v, 2) for k, v in deducted.items() if v},
        "lwop_days": round(lwop, 2),
        "not_deducted_weekly_offs_or_holidays": round(offs, 2),
        "violations": violations,
        "combination_violations": combination_violations,
        "balances": balances,
        "per_day": per_day,
    }
    logger.info(
        f"compute_leave_ledger -> deducted={out['deducted']} lwop={out['lwop_days']} "
        f"violations={len(violations)} combo_violations={len(combination_violations)}"
    )
    return out
