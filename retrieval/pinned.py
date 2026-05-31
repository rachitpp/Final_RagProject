from typing import Dict, List
from langchain_core.documents import Document
from utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Reference lookup tables that almost every query depends on to resolve a
# city/country CATEGORY or a band RATE. They are dense markdown tables that the
# embedder ranks poorly, so on a multi-hop question they get pushed outside the
# candidate cut and silently dropped — exactly when the answer needs them most.
# So we GUARANTEE their presence instead of leaving them to a similarity contest
# they keep losing.
#
# Each table is tagged with its policy and kind so pinning can be policy-aware:
#   - CLASSIFICATION tables (which category a place is) are tiny, and the model
#     needs a category lookup on almost every question, so BOTH policies'
#     classification tables are pinned. This is also a safety net if the
#     upstream trip-type decision is wrong. (This is why the prompt KEEPS its
#     "never cross-apply one policy's categories to the other" guard — both
#     A/B/C tables genuinely coexist in context.)
#   - RATE matrices (the actual amounts, in different currencies) are pinned for
#     the ACTIVE policy ONLY, so a Domestic answer never sees the Foreign $ rate
#     matrix and vice versa. With only one rate system ever present, the prompt
#     no longer needs its "don't mix currencies / DA means different things"
#     guards.
#
# Matched by a stable content signature (whitespace-normalized substring) so
# this survives re-ingestion / chunk-id changes.
# ---------------------------------------------------------------------------
_PINNED = [
    {"sig": "Delhi, Mumbai, Calcutta",             "policy": "domestic", "kind": "classification"},
    {"sig": "LODGING / BOARDING (Rupees per day)", "policy": "domestic", "kind": "rate"},
    {"sig": "Nepal & Bhutan",                      "policy": "foreign",  "kind": "classification"},
    {"sig": "Categories / Countries",              "policy": "foreign",  "kind": "rate"},
]


def _normalize(text: str) -> str:
    """Collapse all whitespace so signatures match regardless of PDF line breaks."""
    return " ".join(text.split())


def resolve_pinned(all_docs: List[Document]) -> Dict[str, Document]:
    """
    Resolve every reference signature to its chunk ONCE (at startup). Returns a
    dict keyed by ``"<policy>_<kind>"`` (e.g. ``"domestic_rate"``). First match
    per signature wins. Missing signatures are logged loudly — if a table stops
    matching after re-ingestion we want to know immediately rather than silently
    regress to "guess the category" behaviour.
    """
    normalized = [(d, _normalize(d.page_content)) for d in all_docs]
    resolved: Dict[str, Document] = {}
    for entry in _PINNED:
        key = f"{entry['policy']}_{entry['kind']}"
        match = next((d for d, norm in normalized if entry["sig"] in norm), None)
        if match is None:
            logger.warning(
                f"Pinned reference table NOT FOUND for signature: {entry['sig']!r}"
            )
            continue
        resolved[key] = match
    logger.info(f"Resolved {len(resolved)} pinned reference table(s).")
    return resolved


def select_pinned(resolved: Dict[str, Document], trip_type: str) -> List[Document]:
    """
    Choose which reference tables to inject for this trip type:
      - BOTH classification tables (active policy first, then the other as a
        safety net),
      - ONLY the active policy's rate matrix.
    De-duped by content, in a stable, logical order.
    """
    other = "foreign" if trip_type == "domestic" else "domestic"
    order = [
        f"{trip_type}_classification",
        f"{other}_classification",
        f"{trip_type}_rate",
    ]
    pinned: List[Document] = []
    seen: set[str] = set()
    for key in order:
        doc = resolved.get(key)
        if doc is None or doc.page_content in seen:
            continue
        seen.add(doc.page_content)
        pinned.append(doc)
    logger.info(f"Pinned {len(pinned)} table(s) for trip_type={trip_type!r}.")
    return pinned
