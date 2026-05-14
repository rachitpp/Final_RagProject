from typing import Iterator
from langsmith import traceable

from ingestion.vector_store import load_vector_store
from retrieval.retrievers import (
    build_bm25_retriever,
    build_vector_retriever,
    hybrid_retrieve,
)
from retrieval.reranker import build_cross_encoder, rerank_and_filter
from retrieval.formatter import format_docs
from retrieval.hyde import generate_hyde
from retrieval.rewrite import rewrite_query
from conversation.memory import ConversationMemory
from llm.models import get_llm
from llm.prompts import ANSWER_PROMPT
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

NO_CONTEXT_FALLBACK = (
    "I could not find anything in the documents that confidently answers "
    "this question. Try rephrasing or asking something more specific."
)


class RAGPipeline:
    """
    End-to-end retrieval pipeline. One class, built once, reused.
    Holds the heavy objects (vector store, BM25 index, cross-encoder,
    LLM, memory). Everything else is a plain function.
    """

    def __init__(self) -> None:
        store = load_vector_store()
        self.bm25 = build_bm25_retriever(store)
        self.vector = build_vector_retriever(store)
        self.cross_encoder = build_cross_encoder()
        self.llm = get_llm(streaming=True)
        self.memory = ConversationMemory(max_turns=settings.history_window)
        logger.info("RAG pipeline initialized.")


    @traceable(
        name="rag_pipeline.retrieve",
        metadata={
            "retriever": "hyde+bm25+vector-mmr",
            "rerank": "ms-marco-MiniLM-L-6-v2",
        },
    )
    def _retrieve(self, query: str) -> tuple[list, str]:
        """Rewrite → HYDE → hybrid retrieve → rerank. Returns (kept_docs, rewritten_query)."""
        rewritten = rewrite_query(query, self.memory.turns())
        hyde_doc = generate_hyde(rewritten) if settings.hyde_enabled else rewritten
        candidates = hybrid_retrieve(
            bm25_query=rewritten,
            vector_query=hyde_doc,
            bm25_retriever=self.bm25,
            vector_retriever=self.vector,
        )
        kept = rerank_and_filter(rewritten, candidates, self.cross_encoder)
        return kept, rewritten

    def stream_answer(self, query: str) -> Iterator[str]:
        """Run the full pipeline and yield the answer token-by-token."""
        kept, rewritten = self._retrieve(query)

        if not kept:
            yield NO_CONTEXT_FALLBACK
            self.memory.add(query, NO_CONTEXT_FALLBACK)
            return

        context = format_docs(kept)
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
