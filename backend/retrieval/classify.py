from dataclasses import dataclass

from langsmith import traceable

from llm.models import get_llm
from llm.prompts import CLASSIFY_PROMPT
from config.documents import ALL_SCOPES
from utils.logger import get_logger

logger = get_logger(__name__)

# Small non-streaming LLM for routing; cached. A short list of labels fits in a
# handful of tokens.
_llm = None


def _classify_llm():
    global _llm
    if _llm is None:
        _llm = get_llm(streaming=False, max_tokens=24)
    return _llm


@dataclass(frozen=True)
class Route:
    """The routing decision for one query.

    scopes    : the policy scopes to retrieve from — a subset of ALL_SCOPES
                (domestic | foreign | leave). Empty () means off-topic / greeting
                (the pipeline asks the user to clarify instead of retrieving).
    trip_type : the travel scope in play ('domestic' | 'foreign'), or None when
                the query is leave-only — drives pinning + the answer grounding.
    assumed   : True when a trip was implied but the destination was unclear and
                we defaulted to Domestic (surfaced to the user in the answer).
    error     : True when routing itself FAILED (the router LLM was unreachable
                after a retry). Distinct from assumed: an ambiguous destination
                is a policy tie-break ("assume Domestic" is doctrine — see
                backend/CLAUDE.md); an infrastructure failure is not a routing
                signal at all, so the pipeline answers honestly instead of
                guessing a scope (a leave question must never silently get the
                domestic travel corpus + travel prompt).
    """
    scopes: tuple[str, ...]
    trip_type: str | None
    assumed: bool
    error: bool = False


def _parse_route(raw: str) -> Route:
    """Parse the router LLM's raw label output into a Route. Pure (no LLM call),
    so it is unit-testable on its own."""
    up = raw.upper()
    scopes = [s for s in ALL_SCOPES if s.upper() in up]

    assumed = False
    if "AMBIGUOUS" in up and not any(s in ("domestic", "foreign") for s in scopes):
        # A trip is implied but the destination is unclear -> default Domestic.
        scopes.append("domestic")
        assumed = True

    if not scopes:
        if "NONE" in up:
            return Route(scopes=(), trip_type=None, assumed=False)
        # Unparseable / empty -> conservative travel default (old behaviour).
        logger.info(f"Router output unparseable ({raw!r}); assuming domestic")
        return Route(scopes=("domestic",), trip_type="domestic", assumed=True)

    ordered = tuple(s for s in ALL_SCOPES if s in scopes)
    trip_type = (
        "foreign" if "foreign" in scopes
        else "domestic" if "domestic" in scopes
        else None
    )
    return Route(scopes=ordered, trip_type=trip_type, assumed=assumed)


@traceable(name="route_query")
def route_query(query: str) -> Route:
    """Route a query to the policy scope(s) it concerns in ONE structured LLM
    call. The result drives scope-filtered retrieval and capability gating
    (pinning / calculator / band are travel-only).

    Failure handling: retry the call once (transient Vertex hiccups are the
    common case), then return Route(error=True) so the pipeline tells the user
    plainly instead of guessing. The old behaviour — default to the domestic
    corpus + travel prompt — gave a leave question a confident travel answer
    with a nonsense "Domestic — ASSUMED" caveat. The AMBIGUOUS-destination
    tie-break (a successful call, unclear destination) still defaults to
    Domestic in _parse_route, per backend/CLAUDE.md."""
    messages = CLASSIFY_PROMPT.format_messages(question=query)
    raw = None
    for attempt in (1, 2):
        try:
            raw = (_classify_llm().invoke(messages).content or "").strip()
            break
        except Exception as e:
            logger.warning(f"Routing attempt {attempt} failed ({e!r})")
    if raw is None:
        logger.error("Routing failed after retry; answering with an honest error")
        return Route(scopes=(), trip_type=None, assumed=False, error=True)

    route = _parse_route(raw)
    logger.info(
        f"Routed {query[:60]!r} -> scopes={route.scopes} "
        f"trip_type={route.trip_type} assumed={route.assumed}"
    )
    return route
