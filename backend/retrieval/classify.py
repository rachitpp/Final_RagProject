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
    """
    scopes: tuple[str, ...]
    trip_type: str | None
    assumed: bool


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
    (pinning / calculator / band are travel-only). Defaults to Domestic on any
    failure, so the pipeline always has something to retrieve."""
    try:
        messages = CLASSIFY_PROMPT.format_messages(question=query)
        raw = (_classify_llm().invoke(messages).content or "").strip()
    except Exception as e:
        logger.warning(f"Routing failed ({e!r}); assuming domestic")
        return Route(scopes=("domestic",), trip_type="domestic", assumed=True)

    route = _parse_route(raw)
    logger.info(
        f"Routed {query[:60]!r} -> scopes={route.scopes} "
        f"trip_type={route.trip_type} assumed={route.assumed}"
    )
    return route
