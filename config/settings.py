# =============================================================
# Central configuration.
# Edit values here; no other module hardcodes settings.
# =============================================================
from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class Settings:
    # --- Paths ---
    pdf_path: str = "pdf"  # file OR folder of PDFs

    # --- Chunking ---
    chunk_size: int = 1000
    chunk_overlap: int = 200
    chunk_separators: List[str] = field(
        default_factory=lambda: ["\n\n", "\n", ". ", " ", ""]
    )

    # --- Embeddings (Vertex AI) ---
    embedding_model: str = "text-embedding-004"
    embedding_location: str = "us-central1"
    embedding_batch_size: int = 200

    # --- LLM (Gemini via Vertex AI) ---
    llm_model: str = "gemini-2.5-flash"
    llm_location: str = "us-central1"
    llm_temperature: float = 0.0   # deterministic: same question -> same answer
    llm_max_tokens: int = 2048

    # --- Vector store (Qdrant Cloud) ---
    qdrant_url: str = "https://d42fb55f-4096-4fbf-8b02-a438145dfd84.us-east4-0.gcp.cloud.qdrant.io"  # from Qdrant Cloud dashboard
    qdrant_collection: str = "rag_documents"
    qdrant_vector_size: int = 768          # text-embedding-004 -> 768 dims

    # --- Retrieval ---
    vector_k: int = 10         # final chunks from vector retriever
    vector_fetch_k: int = 30   # candidates before MMR diversification
    vector_mmr_lambda: float = 0.5  # 0=diversity, 1=relevance
    bm25_k: int = 10

    # --- Reranking + confidence filter ---
    cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    # On this small, tabular corpus ms-marco-MiniLM mis-ranks answer-bearing
    # chunks (e.g. a bare city-classification list) to the bottom, so an
    # aggressive top_n drops exactly what's needed for multi-hop questions
    # ("Pune rate" needs the city->category chunk AND the band->rate chunk).
    # We keep all retrieved candidates and let the cross-encoder only ORDER
    # them. Revisit (lower top_n / better reranker) if the corpus grows large.
    rerank_top_n: int = 20            # max chunks kept after rerank
    # Threshold is on sigmoid(logit) so it lives in [0, 1].
    # NOTE: ms-marco-MiniLM gives near-zero ABSOLUTE scores on this tabular
    # policy corpus (even the answer-bearing rate-matrix chunk scores ~0.000),
    # so ANY positive floor drops the answer and the system falls back to
    # "couldn't find anything". We disable the floor and rely purely on the
    # cross-encoder's RANKING (top_n) plus the LLM's own grounding guardrail.
    rerank_score_threshold: float = 0.0

    # --- HYDE ---
    hyde_enabled: bool = True
    hyde_max_tokens: int = 256

    # --- Conversation memory ---
    history_window: int = 4  # last N (user, assistant) turns kept

    # --- Logging ---
    log_level: str = "WARNING"


settings = Settings()