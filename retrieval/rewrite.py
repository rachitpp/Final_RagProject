import re
from typing import List, Tuple
from langsmith import traceable
from llm.models import get_llm
from llm.prompts import REWRITE_PROMPT
from utils.logger import get_logger

logger = get_logger(__name__)

# Small non-streaming LLM for rewriting; cached.
_llm = None

# A query is treated as a follow-up (and rewritten) only if it contains an
# anaphor / context-dependent reference. Otherwise it is already standalone
# and we pass it through UNCHANGED — rewriting clear questions against stale
# history was corrupting them (e.g. a full "How much can I claim in Pune?"
# came back as "the question is incomplete").
_FOLLOWUP_SIGNALS = re.compile(
    r"\b(it|its|it's|they|them|their|that|this|those|these|there|"
    r"he|she|his|her|same|above|previous|instead|what about|"
    r"and you|then\?)\b",
    re.IGNORECASE,
)


def _looks_like_followup(query: str) -> bool:
    """Short queries or ones with anaphora likely depend on prior context."""
    if len(query.split()) <= 3:
        return True
    return bool(_FOLLOWUP_SIGNALS.search(query))


def _rewrite_llm():
    global _llm
    if _llm is None:
        _llm = get_llm(streaming=False, max_tokens=128)
    return _llm


def _format_history(history: List[Tuple[str, str]]) -> str:
    return "\n".join(
        f"User: {u}\nAssistant: {a}" for u, a in history
    )


@traceable(name="query_rewrite")
def rewrite_query(query: str, history: List[Tuple[str, str]]) -> str:
    """
    Resolve a follow-up question into a standalone one using the
    last few conversation turns. No-op when there is no history.

    Example:
        history: [("What is attention?", "...mechanism in transformers...")]
        query  : "what are its advantages?"
        ->       "What are the advantages of attention mechanisms?"
    """
    if not history:
        return query
    # Only rewrite genuine follow-ups; leave standalone questions intact.
    if not _looks_like_followup(query):
        return query
    try:
        messages = REWRITE_PROMPT.format_messages(
            history=_format_history(history),
            question=query,
        )
        rewritten = _rewrite_llm().invoke(messages).content.strip()
        if rewritten and rewritten.lower() != query.lower():
            logger.info(f"Rewrote: '{query}' -> '{rewritten}'")
            return rewritten
        return query
    except Exception as e:
        logger.warning(f"Rewrite failed ({e!r}); using original query")
        return query
