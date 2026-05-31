from typing import Iterator
from langsmith import traceable

from ingestion.vector_store import load_vector_store
from retrieval.retrievers import (
    build_bm25_retriever,
    build_vector_retriever,
    hybrid_retrieve,
    _scroll_all_docs,
)
from retrieval.pinned import collect_pinned
from retrieval.formatter import format_docs
from retrieval.hyde import generate_hyde
from retrieval.rewrite import rewrite_query
from conversation.memory import ConversationMemory
from llm.models import get_llm
from llm.prompts import ANSWER_PROMPT
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class RAGPipeline:
    """
    End-to-end retrieval pipeline. One class, built once, reused.
    Holds the heavy objects (vector store, BM25 index, LLM, memory).
    Everything else is a plain function.

    Flow: rewrite -> BM25 + vector (union, dedup) -> pin reference tables -> LLM.
    """

    def __init__(self) -> None:
        store = load_vector_store()
        self.bm25 = build_bm25_retriever(store)
        self.vector = build_vector_retriever(store)
        self.llm = get_llm(streaming=True)
        self.memory = ConversationMemory(max_turns=settings.history_window)
        # Reference lookup tables (city/country classification, rate matrices)
        # are resolved ONCE at startup and injected into every query's context,
        # so retrieval — not the prompt — guarantees the category/rate data is
        # present. See retrieval/pinned.py.
        self.pinned = collect_pinned(_scroll_all_docs(store))
        logger.info("RAG pipeline initialized.")

    def _merge_pinned(self, kept: list) -> list:
        """Prepend the pinned reference tables, deduped against the reranked docs."""
        seen = {d.page_content for d in self.pinned}
        return self.pinned + [d for d in kept if d.page_content not in seen]


    @traceable(
        name="rag_pipeline.retrieve",
        metadata={"retriever": "bm25+vector-similarity+pinned-tables"},
    )
    def _retrieve(self, query: str) -> tuple[list, str]:
        """Rewrite → hybrid retrieve → pin reference tables. Returns (context_docs, rewritten_query)."""
        rewritten = rewrite_query(query, self.memory.turns())
        vector_query = generate_hyde(rewritten) if settings.hyde_enabled else rewritten
        candidates = hybrid_retrieve(
            bm25_query=rewritten,
            vector_query=vector_query,
            bm25_retriever=self.bm25,
            vector_retriever=self.vector,
        )
        # Guarantee the reference tables are present regardless of how the
        # retrievers ranked them.
        return self._merge_pinned(candidates), rewritten

    def stream_answer(self, query: str) -> Iterator[str]:
        """Run the full pipeline and yield the answer token-by-token."""
        context_docs, rewritten = self._retrieve(query)

        context = format_docs(context_docs)
        messages = ANSWER_PROMPT.format_messages(
            context=context, question=rewritten
        )

        collected: list[str] = []
        for chunk in self.llm.stream(messages):
            piece = getattr(chunk, "content", None) or ""
            if piece:
                collected.append(piece)
                yield piece

        self.memory.add(query, "".join(collected))
