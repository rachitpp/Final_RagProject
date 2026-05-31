from typing import List
from langchain_core.documents import Document
from utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Reference lookup tables that almost every query depends on to resolve a
# city/country CATEGORY or a band RATE. They are dense markdown tables that
# the embedder + cross-encoder rank poorly (often ~0.000), so on a multi-hop
# question they get pushed outside the candidate cut and silently dropped —
# which is exactly when the answer needs them most.
#
# Instead of leaving them to a similarity contest they keep losing, we
# GUARANTEE their presence. Retrieval owns "is the reference data here?"; the
# prompt is then free to assume it is, and look up rather than guess.
#
# Matched by a stable content signature (whitespace-normalized substring) so
# this survives re-ingestion / chunk-id changes. The loader now stitches the
# domestic rate matrix back into a single self-describing table (all four band
# groups in one chunk), so one signature covers the whole matrix.
# ---------------------------------------------------------------------------
_PINNED_SIGNATURES = [
    "Delhi, Mumbai, Calcutta",              # domestic city classification (A/B/C)
    "LODGING / BOARDING (Rupees per day)",  # domestic rate matrix (all bands)
    "Nepal & Bhutan",                       # foreign country classification (A/B/C)
    "Categories / Countries",               # foreign DA rate matrix ($)
]


def _normalize(text: str) -> str:
    """Collapse all whitespace so signatures match regardless of PDF line breaks."""
    return " ".join(text.split())


def collect_pinned(all_docs: List[Document]) -> List[Document]:
    """
    Return the reference-table chunks in a fixed, logical order. First match
    per signature wins. Missing signatures are logged loudly — if the corpus
    is re-ingested and a table stops matching, we want to know immediately
    rather than silently regress to the old "guess the category" behavior.
    """
    normalized = [(d, _normalize(d.page_content)) for d in all_docs]
    pinned: List[Document] = []
    seen: set[str] = set()
    for sig in _PINNED_SIGNATURES:
        match = next((d for d, norm in normalized if sig in norm), None)
        if match is None:
            logger.warning(f"Pinned reference table NOT FOUND for signature: {sig!r}")
            continue
        # Two signatures can resolve to the same chunk (e.g. if tables merge);
        # don't inject it twice.
        if match.page_content in seen:
            continue
        seen.add(match.page_content)
        pinned.append(match)
    logger.info(f"Pinned {len(pinned)} reference table(s).")
    return pinned
