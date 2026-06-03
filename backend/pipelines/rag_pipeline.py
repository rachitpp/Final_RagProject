from typing import Iterator
from langsmith import traceable

from ingestion.vector_store import load_vector_store
from retrieval.retrievers import (
    build_bm25_retriever,
    build_bm25_by_policy,
    hybrid_retrieve,
    _scroll_all_docs,
)
from retrieval.pinned import resolve_pinned, select_pinned
from retrieval.classify import classify_trip_type
from retrieval.formatter import format_docs
from retrieval.hyde import generate_hyde
from retrieval.rewrite import rewrite_query
from llm.models import get_llm
from llm.prompts import ANSWER_PROMPT
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


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

    Flow: rewrite -> classify policy -> policy-scoped BM25 + vector (union,
    dedup) -> pin reference tables (both classifications + active rate) -> LLM.

    Policy isolation is owned by RETRIEVAL, not the prompt: the trip type is
    decided once (classify_trip_type) and that single decision drives the body
    filter, which rate table is pinned, and the prompt's grounding line — so
    they can never disagree.
    """

    def __init__(self) -> None:
        store = load_vector_store()
        self.store = store
        # Combined index — used by the sidebar's Library view (lists all docs).
        self.bm25 = build_bm25_retriever(store)
        # Per-policy indexes — used for policy-scoped keyword retrieval.
        self.bm25_by_policy = build_bm25_by_policy(store)
        self.llm = get_llm(streaming=True)
        # Reference tables resolved ONCE at startup. select_pinned() then picks
        # the right subset per query based on trip type. See retrieval/pinned.py.
        self.pinned = resolve_pinned(_scroll_all_docs(store))
        logger.info("RAG pipeline initialized.")

    def _merge_pinned(self, kept: list, trip_type: str) -> list:
        """Prepend the pinned reference tables for this trip type, deduped
        against the retrieved docs."""
        pinned = select_pinned(self.pinned, trip_type)
        seen = {d.page_content for d in pinned}
        return pinned + [d for d in kept if d.page_content not in seen]

    @traceable(
        name="rag_pipeline.retrieve",
        metadata={"retriever": "classify+bm25+vector-similarity+pinned-tables"},
    )
    def _retrieve(self, query: str, history: list) -> tuple[list, str, str, bool]:
        """Rewrite → classify policy → policy-scoped hybrid retrieve → pin
        reference tables. Returns (context_docs, rewritten_query, trip_type,
        assumed)."""
        rewritten = rewrite_query(query, history)
        trip_type, assumed = classify_trip_type(rewritten)
        vector_query = generate_hyde(rewritten) if settings.hyde_enabled else rewritten
        candidates = hybrid_retrieve(
            bm25_query=rewritten,
            vector_query=vector_query,
            store=self.store,
            bm25_by_policy=self.bm25_by_policy,
            policy=trip_type,
        )
        # Guarantee the reference tables are present regardless of ranking.
        return self._merge_pinned(candidates, trip_type), rewritten, trip_type, assumed

    def stream_answer(
        self, query: str, history: list | None = None
    ) -> Iterator[str]:
        """Run the full pipeline and yield the answer token-by-token.

        `history` is a list of prior (user, assistant) turns, used ONLY to
        resolve follow-ups during rewrite. The pipeline stores nothing; the
        caller appends the completed turn to its own memory.
        """
        context_docs, rewritten, trip_type, assumed = self._retrieve(
            query, history or []
        )

        context = format_docs(context_docs)
        messages = ANSWER_PROMPT.format_messages(
            context=context,
            question=rewritten,
            trip_type=_trip_label(trip_type, assumed),
        )

        for chunk in self.llm.stream(messages):
            piece = getattr(chunk, "content", None) or ""
            if piece:
                yield piece
