import re
from typing import List, Tuple
from langsmith import traceable
from config.settings import settings
from llm.models import get_llm
from llm.prompts import REWRITE_PROMPT
from utils.logger import get_logger

logger = get_logger(__name__)

# Small non-streaming LLM for rewriting; cached.
_llm = None

# A query is treated as a follow-up (and rewritten) only if it carries a
# genuinely context-dependent signal. Otherwise it is already standalone and
# we pass it through UNCHANGED — rewriting clear questions against stale
# history was corrupting them (e.g. a full "How much can I claim in Pune?"
# came back as "the question is incomplete").
#
# Each false positive costs a serial LLM round-trip before retrieval even
# starts, so the signals are deliberately narrow:
#   - true pronouns (it / they / them / he / she ...) — near-always anaphoric
#     in a question ("can I claim it?");
#   - explicit continuation phrases ("what about", "the same", "instead", ...).
# Bare function words the old gate matched (that / this / there / same / those)
# are ubiquitous in standalone English ("Is there a cap on lodging?", "cities
# that aren't listed") and are NOT signals on their own.
_FOLLOWUP_SIGNALS = re.compile(
    r"\b(it|its|it's|they|them|their|theirs|he|she|his|hers|her)\b"
    r"|\b(what about|how about|the same|that one|this one|those ones"
    r"|as well|instead|above|previous|previously|and you|then\?)",
    re.IGNORECASE,
)

# Elliptical follow-ups often LEAD with a continuer rather than containing a
# pronoun: "And for foreign trips?", "Also for band C?", "But with bills?".
# Sentence-initial only — "and"/"but" mid-sentence is just English.
_FOLLOWUP_OPENERS = re.compile(
    r"^\s*(and|but|also|then|so|ok|okay|now|what about|how about|same)\b",
    re.IGNORECASE,
)


def _looks_like_followup(query: str) -> bool:
    """Short queries, continuer openings, or anaphora likely depend on prior
    context; everything else is treated as standalone (no rewrite call)."""
    if len(query.split()) <= 3:
        return True
    if _FOLLOWUP_OPENERS.search(query):
        return True
    return bool(_FOLLOWUP_SIGNALS.search(query))


def _rewrite_llm():
    global _llm
    if _llm is None:
        _llm = get_llm(streaming=False, max_tokens=128)
    return _llm


def _format_history(history: List[Tuple[str, str]]) -> str:
    """Render only what reference-resolution needs: the last few turns, with
    each assistant answer clipped. Full answers carry whole rate tables, so an
    untruncated history made the rewrite prompt itself thousands of tokens."""
    recent = history[-settings.rewrite_history_turns:]
    clip = settings.rewrite_history_clip_chars

    def _clip(text: str) -> str:
        return text if len(text) <= clip else text[:clip].rstrip() + " …"

    return "\n".join(f"User: {u}\nAssistant: {_clip(a)}" for u, a in recent)


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
