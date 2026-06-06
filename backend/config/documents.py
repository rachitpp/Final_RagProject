# =============================================================
# Document registry — the single source of truth for what each
# policy PDF is. Replaces filename-sniffing in the loader.
# =============================================================
"""
Maps each PDF's filename to its retrieval SCOPE (``domestic | foreign | leave``)
— the always-present key retrieval isolates on — and maps each scope to the
post-retrieval capabilities its answers need. The loader stamps ``scope`` on
every chunk from this; the retriever filters on it; the pipeline gates
travel-only machinery (pinned rate tables, the ``compute_entitlement``
calculator, band injection) on the capabilities of the scopes a query touches.

Add a policy PDF = add one row to ``FILE_SCOPES`` (and a ``SCOPE_CAPABILITIES``
entry only if it introduces a new scope), drop the file in ``pdf/``, re-ingest.
No other file changes.
"""
import os

# PDF filename (basename, lowercased) -> retrieval scope.
FILE_SCOPES: dict[str, str] = {
    "domestic travel.pdf": "domestic",
    "foreign.pdf": "foreign",
    "leave.pdf": "leave",
}

# Scope -> the post-retrieval machinery its answers need.
#   pin_tables   : guarantee the rate/classification reference tables in context
#   calculator   : offer the compute_entitlement tool (travel totals)
#   band         : inject the user's band into the answer prompt
#   leave_ledger : offer the compute_leave_ledger tool (leave dates/balances/LWOP)
# Leave is band-agnostic (no rate tables) but is temporally complex, so it needs
# the deterministic ledger.
SCOPE_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "domestic": ("pin_tables", "calculator", "band"),
    "foreign": ("pin_tables", "calculator", "band"),
    "leave": ("leave_ledger",),
}

# Scope -> employee-facing display title for the UI's "Policies" list. The
# retrieval scope IS the policy's identity, so titles key off it (same shape as
# SCOPE_CAPABILITIES). Keeps the sidebar from showing raw filenames like
# "domestic travel.pdf"; the frontend maps the scope to an icon.
SCOPE_TITLES: dict[str, str] = {
    "domestic": "Domestic Travel",
    "foreign": "Foreign Travel",
    "leave": "Leave",
}

# Used only if an untracked PDF is ingested; the loader logs a warning so this
# is never silent (the old filename-sniffing mis-tagged leave.pdf as domestic).
DEFAULT_SCOPE = "domestic"

ALL_SCOPES: tuple[str, ...] = tuple(SCOPE_CAPABILITIES)


def scope_for(filename: str) -> str:
    """Resolve a PDF filename to its scope (DEFAULT_SCOPE if untracked)."""
    return FILE_SCOPES.get(os.path.basename(filename).lower(), DEFAULT_SCOPE)


def capabilities_for(scopes) -> set[str]:
    """Union of capabilities across the given scopes (for query-time gating)."""
    caps: set[str] = set()
    for s in scopes:
        caps.update(SCOPE_CAPABILITIES.get(s, ()))
    return caps


def _prettify(filename: str) -> str:
    """Fallback title for an untracked PDF: 'some_policy.pdf' -> 'Some Policy'."""
    stem = os.path.splitext(os.path.basename(filename))[0]
    return " ".join(stem.replace("_", " ").replace("-", " ").split()).title()


def title_for(filename: str) -> str:
    """Employee-facing title for a PDF — its registry title, else a prettified
    filename (untracked files fall through rather than borrowing DEFAULT_SCOPE's
    title, which would mislabel them)."""
    scope = FILE_SCOPES.get(os.path.basename(filename).lower())
    return SCOPE_TITLES[scope] if scope in SCOPE_TITLES else _prettify(filename)


def topic_for(filename: str) -> str:
    """Topic key the UI maps to an icon — the scope for tracked files, else
    'policy' (a neutral default, never the misleading DEFAULT_SCOPE)."""
    return FILE_SCOPES.get(os.path.basename(filename).lower(), "policy")
