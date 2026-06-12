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
# ONLY the ACTIVE policy's tables (classification + rate matrix) are pinned,
# now that retrieval is scope-filtered — a Domestic answer never sees the
# Foreign $ rate matrix and vice versa, and a leave query pins nothing. With a
# single policy's tables ever present, the prompt needs no "don't cross-apply
# categories / don't mix currencies" guards. (An older design pinned BOTH
# policies' classification tables as a safety net; that ended with the move to
# scope-filtered retrieval — see select_pinned.)
#
# Matched by a stable content signature (whitespace-normalized substring) so
# this survives re-ingestion / chunk-id changes.
# ---------------------------------------------------------------------------
_PINNED = [
    {"sig": "Delhi, Mumbai, Calcutta",             "policy": "domestic", "kind": "classification"},
    {"sig": "LODGING / BOARDING (Rupees per day)", "policy": "domestic", "kind": "rate"},
    # Foreign: one JOINED table (country category + countries + per-band rate in
    # the same row, from the curated foreign.tables.md). The model kept resolving
    # a by-exclusion country to Category C correctly but then reading the rate
    # from a different row of the separate rate table; joining the category list
    # and the rates removes that cross-table hop. Replaces the old split
    # classification + rate pins (which are still retrievable, just not pinned).
    {"sig": "Countries in this category",          "policy": "foreign",  "kind": "rate"},
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
      - the active policy's classification table,
      - the active policy's rate matrix.
    Only the active scope's tables are pinned now that retrieval is
    scope-filtered (a leave query pins nothing), so the answer prompt no longer
    needs a "don't cross-apply the other policy's categories" guard.
    De-duped by content, in a stable, logical order.
    """
    order = [
        f"{trip_type}_classification",
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
