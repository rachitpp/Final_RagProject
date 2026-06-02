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
from typing import List
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
