import json
from datetime import date
from typing import Iterator, Protocol
from langsmith import traceable
from langchain_core.messages import ToolMessage

from ingestion.vector_store import load_vector_store
from retrieval.retrievers import (
    assert_scope_tagged,
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
    EMPLOYEE_LEAVE_RECORD,
    PERSONALIZATION_CONTEXT,
    GREETING_FIRST_TURN,
    GREETING_LATER_TURN,
)
from llm.tools import compute_entitlement, compute_leave_ledger
from config.documents import capabilities_for
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class UserContext(Protocol):
    """Structural type for the authenticated caller. The pipeline reads the
    band (travel answer scoping), name (friendly greeting/tone), and the leave
    record (date_of_joining + leave_taken, for personal balance questions), so
    it depends on this shape — not on api.schemas.UserProfile — keeping the
    retrieval layer decoupled from the web layer. UserProfile satisfies it."""
    band: int
    name: str
    date_of_joining: "date | None"
    leave_taken: dict[str, float] | None


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
        # Fail fast on an untagged corpus: every retrieval leg isolates on the
        # `scope` tag, so booting against a pre-scope corpus can only produce
        # wrong (cross-policy) answers. Refusing to start beats the old
        # per-query unfiltered fallback that leaked across scopes silently.
        assert_scope_tagged(docs)
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
        # A rewrite may only ever ADD context, never subtract it — but the
        # rewriter occasionally paraphrases away a load-bearing term (observed:
        # "surge pricing" dropped, so the surge clause was never retrieved).
        # The keyword leg therefore searches the UNION of both phrasings; BM25
        # is bag-of-words, so concatenation can only widen recall.
        bm25_query = query if rewritten == query else f"{query}\n{rewritten}"
        vector_query = generate_hyde(rewritten) if settings.hyde_enabled else rewritten
        candidates = multi_scope_retrieve(
            bm25_query=bm25_query,
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
        We read `.band` and `.name` from it: when a band is known and a TRAVEL
        scope is active, we inject it so the answer is scoped to that band
        instead of the all-bands fallback; the name drives the friendly tone
        (first-turn greeting + contextual follow-up). Duck-typed to keep the
        pipeline decoupled from the API layer. Leave is band-agnostic, so the
        band is never used there.

        If the model calls the calculator, we run it, feed the exact results
        back, and stream the next round — so tool rounds stay invisible and
        only the final prose reaches the user.
        """
        # Friendly-tone inputs: the caller's first name (server-authoritative,
        # same profile the band comes from) and whether this is the
        # conversation's first turn — we greet by name only on the first turn.
        full_name = getattr(user_profile, "name", None)
        first_name = full_name.split()[0] if full_name else None
        is_first_turn = not history

        context_docs, rewritten, route = self._retrieve(query, history or [])

        # Routing infrastructure failed (after a retry): say so honestly. The
        # old behaviour — guess Domestic — gave e.g. a leave question a
        # confident travel answer; an error the user can retry is strictly
        # better than a wrong answer they can't detect.
        if route.error:
            yield (
                "Sorry — I couldn't process that question right now due to a "
                "temporary issue. Please try asking it again."
            )
            return

        # Off-topic / greeting -> ask to clarify rather than retrieve noise.
        # Greet by name here too (canned path, so the greeting is ours to add):
        # "hi" as a first message gets "Hi Rahul! I can help with ...".
        if not route.scopes:
            greeting = f"Hi {first_name}! " if first_name and is_first_turn else ""
            yield (
                f"{greeting}I can help with the company's travel-reimbursement "
                "and leave policies. Could you rephrase your question around "
                "one of those?"
            )
            return

        context = format_docs(context_docs)
        caps = capabilities_for(route.scopes)

        # The answer model gets BOTH phrasings when they differ: the rewritten
        # form resolves follow-up references, but the user's original wording is
        # authoritative for details the rewriter may have dropped or imported
        # from history (see _retrieve's union note).
        question = (
            rewritten if rewritten == query
            else (
                f"{query}\n(Standalone restatement for context — the wording "
                f"above is authoritative where they differ: {rewritten})"
            )
        )

        # Friendly tone, both prompts alike: greet by first name on the first
        # turn only, and close grounded answers with one contextual follow-up.
        # Anonymous caller (CLI, tests) -> empty slot, impersonal answers.
        if first_name:
            greeting_line = (
                GREETING_FIRST_TURN.format(name=first_name)
                if is_first_turn else GREETING_LATER_TURN
            )
            personalization = PERSONALIZATION_CONTEXT.format(
                name=first_name, greeting_line=greeting_line
            )
        else:
            personalization = ""

        # Personal leave record (same authority model as the band): when the
        # LEAVE scope is active and the caller's joining date + usage are on
        # file, inject them so "how many CL do I have left?" resolves from the
        # server-side record — compute_leave_ledger does the remaining math.
        # An all-zero record still injects (zero taken is a real record); only
        # a missing profile/DOJ falls back to the impersonal behaviour.
        leave_record = ""
        if "leave" in route.scopes:
            taken = getattr(user_profile, "leave_taken", None)
            doj = getattr(user_profile, "date_of_joining", None)
            if taken and doj is not None:
                leave_record = EMPLOYEE_LEAVE_RECORD.format(
                    doj=doj.isoformat(),
                    taken=json.dumps(taken),
                    today=date.today().isoformat(),
                )

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
                question=question,
                trip_type=_trip_label(route.trip_type, route.assumed),
                employee_context=employee_context,
                personalization=personalization,
            )
            if "leave" in route.scopes:
                messages[0].content = (
                    messages[0].content + "\n\n" + LEAVE_ADDENDUM
                    + (("\n\n" + leave_record) if leave_record else "")
                )
        else:
            # Leave-only: no travel machinery, no calculator.
            messages = LEAVE_ANSWER_PROMPT.format_messages(
                context=context, question=question,
                personalization=personalization,
                employee_context=leave_record,
            )

        # Bind only the tools the active scopes' capabilities unlock
        # (travel -> calculator, leave -> ledger); plain LLM if none.
        tools = [self._cap_tools[c] for c in self._cap_tools if c in caps]
        llm = self.llm.bind_tools(tools) if tools else self.llm

        # Each round's prose is buffered until the round ENDS, because only
        # then do we know whether it was a tool round. The model sometimes
        # writes a complete (uncalculated, possibly wrong) answer and only THEN
        # emits the tool call — any prose streamed live before that point can't
        # be retracted, and the user would see two contradictory answers. So a
        # round that ends in tool calls has its prose discarded wholesale, and
        # only a tool-free round's prose reaches the user.
        for _ in range(_MAX_TOOL_ROUNDS):
            gathered = None
            prose: list[str] = []  # held until we know the round's nature
            for chunk in llm.stream(messages):
                gathered = chunk if gathered is None else gathered + chunk
                piece = getattr(chunk, "content", None) or ""
                if piece:
                    prose.append(piece)

            tool_calls = getattr(gathered, "tool_calls", None) if gathered else None
            if not tool_calls:
                if prose:
                    yield "".join(prose)
                return  # no tool requested -> the answer is complete

            # Tool round: drop its prose, record the model's request + each
            # result, then loop for the post-tool answer.
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
