from langsmith import traceable
from llm.models import get_llm
from llm.prompts import CLASSIFY_PROMPT
from utils.logger import get_logger

logger = get_logger(__name__)

# Small non-streaming LLM for routing; cached.
_llm = None


def _classify_llm():
    global _llm
    if _llm is None:
        _llm = get_llm(streaming=False, max_tokens=8)
    return _llm


@traceable(name="classify_trip_type")
def classify_trip_type(query: str) -> tuple[str, bool]:
    """
    Decide which policy applies: ``"domestic"`` (within India) or ``"foreign"``
    (overseas). Returns ``(policy, assumed)`` where ``assumed`` is True when the
    destination was ambiguous and we fell back to Domestic.

    This is the SINGLE source of truth for policy routing. Both retrieval (the
    body filter + which rate table is pinned) and the answer prompt's grounding
    line consume this one decision, so they can never silently disagree. The
    "assume Domestic when ambiguous" tie-break lives here — not in the answer
    prompt — for exactly that reason.

    On any failure, defaults conservatively to Domestic (assumed=True).
    """
    try:
        messages = CLASSIFY_PROMPT.format_messages(question=query)
        raw = (_classify_llm().invoke(messages).content or "").strip().lower()
    except Exception as e:
        logger.warning(f"Trip-type classify failed ({e!r}); assuming domestic")
        return "domestic", True

    if "foreign" in raw:
        return "foreign", False
    if "domestic" in raw:
        return "domestic", False
    # "ambiguous" or any unexpected output -> conservative default.
    logger.info(f"Trip-type ambiguous (model said {raw!r}); assuming domestic")
    return "domestic", True
