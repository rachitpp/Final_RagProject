import json
from typing import Iterator, Protocol
from langsmith import traceable
from langchain_core.messages import ToolMessage

from ingestion.vector_store import load_vector_store
from retrieval.retrievers import (
    build_bm25_retriever,
    build_bm25_by_scope,
    multi_scope_retrieve,
    _scroll_all_docs,
)
from retrieval.pinned import resolve_pinned, select_pinned
from retrieval.classify import route_query
from retrieval.formatter import format_docs
from retrieval.hyde import generate_hyde
from retrieval.rewrite import rewrite_query
from llm.models import get_llm
from llm.prompts import (
    ANSWER_PROMPT,
    LEAVE_ANSWER_PROMPT,
    LEAVE_ADDENDUM,
    EMPLOYEE_BAND_CONTEXT,
)
from llm.tools import compute_entitlement, compute_leave_ledger
from config.documents import capabilities_for
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class UserContext(Protocol):
    """Structural type for the authenticated caller. The pipeline reads only the
    band, so it depends on this shape — not on api.schemas.UserProfile — keeping
    the retrieval layer decoupled from the web layer. UserProfile satisfies it."""
    band: int


# The model may need one round to call the calculator and another to write the
# answer; a few rounds is ample headroom, bounded so it can't loop forever.
_MAX_TOOL_ROUNDS = 4


def _trip_label(trip_type: str, assumed: bool) -> str:
    """Human-readable trip-type string fed to the answer prompt's grounding.
    When the policy was assumed (ambiguous destination), the label tells the
    model to surface that assumption to the user."""
    base = (
        "Foreign (overseas travel)"
        if trip_type == "foreign"
        else "Domestic (travel within India)"
    )
    if assumed:
        return (
            base + " — ASSUMED, because no overseas destination was indicated"
        )
    return base


class RAGPipeline:
    """
    End-to-end retrieval pipeline. One class, built once, reused.
    Holds the heavy objects (vector store, BM25 indexes, LLM, pinned tables).

    STATELESS per conversation: it holds no chat history. Each call receives the
    relevant history as an argument, so one shared instance can safely serve many
    concurrent conversations. Storage is owned by the caller (conversation/store.py
    for the web layer; main.py for the CLI).

    Flow: rewrite -> route to scope(s) -> scope-filtered BM25 + vector (union,
    dedup) -> pin reference tables (travel scopes only) -> LLM.

    Scope isolation is owned by RETRIEVAL, not the prompt: routing is decided
    once (route_query) and that single decision drives the scope filter, which
    rate table is pinned (travel only), the calculator gating, and the prompt's
    grounding line — so they can never disagree.

    Arithmetic is owned by CODE, not the model: it reads the rates from the
    retrieved context and calls the `compute_entitlement` tool, which totals
    them exactly — so a multi-day / multi-city sum can't be miscalculated.
    See llm/tools.py.
    """

    def __init__(self) -> None:
        store = load_vector_store()
        self.store = store
        # Scroll the collection ONCE and feed every startup consumer from it
        # (combined BM25, per-scope BM25, pinned tables) — this used to be
        # three identical full scrolls over the network.
        docs = _scroll_all_docs(store)
        # Combined index — used by the sidebar's Library view (lists all docs).
        self.bm25 = build_bm25_retriever(docs)
        # Per-scope indexes — used for scope-scoped keyword retrieval.
        self.bm25_by_scope = build_bm25_by_scope(docs)
        # capability name -> the tool it unlocks; bound per query from the active
        # scopes' capabilities (registry-driven, scales to new tools). Code does
        # the math, the model does the language (llm/tools.py).
        self._cap_tools = {
            "calculator": compute_entitlement,
            "leave_ledger": compute_leave_ledger,
        }
        self._tools = {t.name: t for t in self._cap_tools.values()}
        self.llm = get_llm(streaming=True)
        # Reference tables resolved ONCE at startup. select_pinned() then picks
        # the right subset per query based on trip type. See retrieval/pinned.py.
        self.pinned = resolve_pinned(docs)
        logger.info("RAG pipeline initialized.")

    def _run_tool(self, call: dict) -> str:
        """Execute one tool call and return its result as a JSON string."""
        tool = self._tools.get(call["name"])
        if tool is None:
            return json.dumps({"error": f"unknown tool {call['name']!r}"})
        try:
            return json.dumps(tool.invoke(call["args"]), default=str)
        except Exception as e:
            logger.warning(f"Tool {call['name']} failed: {e!r}")
            return json.dumps({"error": str(e)})

    def _merge_pinned(self, kept: list, trip_type: str) -> list:
        """Prepend the pinned reference tables for this trip type, deduped
        against the retrieved docs."""
        pinned = select_pinned(self.pinned, trip_type)
        seen = {d.page_content for d in pinned}
        return pinned + [d for d in kept if d.page_content not in seen]

    @traceable(
        name="rag_pipeline.retrieve",
        metadata={"retriever": "route+bm25+vector-similarity+pinned-tables"},
    )
    def _retrieve(self, query: str, history: list):
        """Rewrite → route to scope(s) → scope-filtered hybrid retrieve (union)
        → pin reference tables for travel scopes. Returns (context_docs,
        rewritten_query, route)."""
        rewritten = rewrite_query(query, history)
        route = route_query(rewritten)
        if not route.scopes:
            return [], rewritten, route
        vector_query = generate_hyde(rewritten) if settings.hyde_enabled else rewritten
        candidates = multi_scope_retrieve(
            bm25_query=rewritten,
            vector_query=vector_query,
            store=self.store,
            bm25_by_scope=self.bm25_by_scope,
            scopes=route.scopes,
        )
        # Guarantee the reference tables are present (travel scopes only).
        if "pin_tables" in capabilities_for(route.scopes) and route.trip_type:
            candidates = self._merge_pinned(candidates, route.trip_type)
        return candidates, rewritten, route

    def stream_answer(
        self,
        query: str,
        history: list | None = None,
        user_profile: "UserContext | None" = None,
    ) -> Iterator[str]:
        """Run the full pipeline and yield the answer token-by-token.

        `history` is a list of prior (user, assistant) turns, used ONLY to
        resolve follow-ups during rewrite. The pipeline stores nothing; the
        caller appends the completed turn to its own memory.

        `user_profile` is the authenticated caller (or None when anonymous).
        We read only `.band` from it; when a band is known and a TRAVEL scope is
        active, we inject it so the answer is scoped to that band instead of the
        all-bands fallback. Duck-typed to keep the pipeline decoupled from the
        API layer. Leave is band-agnostic, so the band is never used there.

        If the model calls the calculator, we run it, feed the exact results
        back, and stream the next round — so tool rounds stay invisible and
        only the final prose reaches the user.
        """
        context_docs, rewritten, route = self._retrieve(query, history or [])

        # Off-topic / greeting -> ask to clarify rather than retrieve noise.
        if not route.scopes:
            yield (
                "I can help with the company's travel-reimbursement and leave "
                "policies. Could you rephrase your question around one of those?"
            )
            return

        context = format_docs(context_docs)
        caps = capabilities_for(route.scopes)

        if route.trip_type is not None:
            # Travel (optionally + leave): the tuned travel prompt drives it.
            # If we know the caller's band, scope the answer to it (server-
            # authoritative); otherwise the prompt answers for every band.
            band = getattr(user_profile, "band", None)
            employee_context = (
                EMPLOYEE_BAND_CONTEXT.format(band=band) if band is not None else ""
            )
            messages = ANSWER_PROMPT.format_messages(
                context=context,
                question=rewritten,
                trip_type=_trip_label(route.trip_type, route.assumed),
                employee_context=employee_context,
            )
            if "leave" in route.scopes:
                messages[0].content = messages[0].content + "\n\n" + LEAVE_ADDENDUM
        else:
            # Leave-only: no travel machinery, no calculator.
            messages = LEAVE_ANSWER_PROMPT.format_messages(
                context=context, question=rewritten,
            )

        # Bind only the tools the active scopes' capabilities unlock
        # (travel -> calculator, leave -> ledger); plain LLM if none.
        tools = [self._cap_tools[c] for c in self._cap_tools if c in caps]
        llm = self.llm.bind_tools(tools) if tools else self.llm

        for _ in range(_MAX_TOOL_ROUNDS):
            gathered = None
            for chunk in llm.stream(messages):
                piece = getattr(chunk, "content", None) or ""
                if piece:
                    # Stream live, token-by-token. A tool-calling round carries
                    # empty content (the model emits tool calls, not prose), so
                    # nothing leaks here on those rounds — only the real answer
                    # streams out. We still accumulate `gathered` below to read
                    # the round's tool calls and to append the assistant turn.
                    yield piece
                gathered = chunk if gathered is None else gathered + chunk

            tool_calls = getattr(gathered, "tool_calls", None) if gathered else None
            if not tool_calls:
                return  # no tool requested -> the answer is complete

            # Tool round: record the model's request + each result, then loop.
            messages.append(gathered)
            for call in tool_calls:
                messages.append(ToolMessage(
                    content=self._run_tool(call),
                    tool_call_id=call["id"],
                ))

        # Tool rounds exhausted without a final prose answer (the model kept
        # requesting tools). Make ONE last pass with tools unbound so it must
        # write an answer — guaranteeing the user never gets an empty reply.
        for chunk in self.llm.stream(messages):
            piece = getattr(chunk, "content", None) or ""
            if piece:
                yield piece
