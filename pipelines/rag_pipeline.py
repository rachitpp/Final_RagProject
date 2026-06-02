import json
from typing import Iterator
from langsmith import traceable
from langchain_core.messages import ToolMessage

from ingestion.vector_store import load_vector_store
from retrieval.retrievers import vector_search, _scroll_all_docs
from retrieval.pinned import resolve_pinned, select_pinned
from retrieval.classify import classify_trip_type
from retrieval.formatter import format_docs
from retrieval.rewrite import rewrite_query
from conversation.memory import ConversationMemory
from llm.models import get_llm
from llm.prompts import ANSWER_PROMPT
from llm.tools import compute_entitlement
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

# The model may need one round to call the calculator and another to write the
# answer; a couple of extra rounds is ample headroom. Bounded so a misbehaving
# model can never loop forever.
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
    Holds the heavy objects (vector store, LLM, memory).

    Flow: rewrite -> classify policy -> policy-scoped vector search -> pin
    reference tables (both classifications + active rate) -> LLM.

    Policy isolation is owned by RETRIEVAL, not the prompt: the trip type is
    decided once (classify_trip_type) and that single decision drives the body
    filter, which rate table is pinned, and the prompt's grounding line — so
    they can never disagree.

    Arithmetic is owned by CODE, not the model: it reads the rates from the
    retrieved context and calls the `compute_entitlement` tool, which totals
    them exactly — so a multi-day / multi-city sum can't be miscalculated.
    See llm/tools.py.
    """

    def __init__(self) -> None:
        store = load_vector_store()
        self.store = store
        # Every chunk, pulled once at startup. Reused for pinned-table
        # resolution and to populate the sidebar's Library view (lists all docs).
        self.documents = _scroll_all_docs(store)
        self.memory = ConversationMemory(max_turns=settings.history_window)
        # Reference tables resolved ONCE at startup. select_pinned() then picks
        # the right subset per query based on trip type. See retrieval/pinned.py.
        self.pinned = resolve_pinned(self.documents)
        # Bind the calculator so the model can offload every total to exact code.
        self._tools = {compute_entitlement.name: compute_entitlement}
        self.llm = get_llm(streaming=True).bind_tools([compute_entitlement])
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
        metadata={"retriever": "classify+vector-similarity+pinned-tables"},
    )
    def _retrieve(self, query: str) -> tuple[list, str, str, bool]:
        """Rewrite → classify policy → policy-scoped vector search → pin
        reference tables. Returns (context_docs, rewritten_query, trip_type,
        assumed)."""
        rewritten = rewrite_query(query, self.memory.turns())
        trip_type, assumed = classify_trip_type(rewritten)
        candidates = vector_search(self.store, rewritten, trip_type)
        # Guarantee the reference tables are present regardless of ranking.
        return self._merge_pinned(candidates, trip_type), rewritten, trip_type, assumed

    def stream_answer(self, query: str) -> Iterator[str]:
        """Run the full pipeline and yield the answer token-by-token.

        Retrieves the policy-scoped context, then streams the answer. If the
        model asks for the calculator, we run it, feed the exact results back,
        and stream the next round — so tool rounds are transparent and the final
        prose still streams to the user.
        """
        context_docs, rewritten, trip_type, assumed = self._retrieve(query)

        context = format_docs(context_docs)

        messages = ANSWER_PROMPT.format_messages(
            context=context,
            question=rewritten,
            trip_type=_trip_label(trip_type, assumed),
        )

        final_answer_pieces: list[str] = []
        
        for _ in range(_MAX_TOOL_ROUNDS):
            round_pieces: list[str] = []
            gathered = None
            
            for chunk in self.llm.stream(messages):
                piece = getattr(chunk, "content", None) or ""
                if piece:
                    round_pieces.append(piece)
                gathered = chunk if gathered is None else gathered + chunk
            
            tool_calls = getattr(gathered, "tool_calls", None) if gathered else None
            
            if not tool_calls:
                # Final answer - yield and store
                final_answer = "".join(round_pieces)
                for char in final_answer:
                    yield char
                final_answer_pieces.append(final_answer)
                break
            
            # Tool call round - accumulate without yielding
            messages.append(gathered)
            for call in tool_calls:
                messages.append(ToolMessage(
                    content=self._run_tool(call),
                    tool_call_id=call["id"],
                ))
        
        # Add to memory after all streaming is done
        self.memory.add(query, "".join(final_answer_pieces))