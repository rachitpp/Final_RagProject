# =============================================================
# Central configuration.
# Edit values here; no other module hardcodes settings.
# =============================================================
from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class Settings:
    # --- Paths ---
    pdf_path: str = "MachineLearning.pdf"  # file OR folder of PDFs

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
    llm_temperature: float = 0.2
    llm_max_tokens: int = 1024

    # --- Vector store (Qdrant Cloud) ---
    qdrant_url: str = "https://d42fb55f-4096-4fbf-8b02-a438145dfd84.us-east4-0.gcp.cloud.qdrant.io"  # from Qdrant Cloud dashboard
    qdrant_collection: str = "rag_documents"
    qdrant_vector_size: int = 768          # text-embedding-004 -> 768 dims

    # --- Retrieval ---
    vector_k: int = 5          # final chunks from vector retriever
    vector_fetch_k: int = 20   # candidates before MMR diversification
    vector_mmr_lambda: float = 0.5  # 0=diversity, 1=relevance
    bm25_k: int = 5

    # --- Reranking + confidence filter ---
    cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rerank_top_n: int = 5             # max chunks kept after rerank
    # Threshold is on sigmoid(logit) so it lives in [0, 1].
    # 0.5 = "model thinks chunk is more relevant than not". Tune per corpus.
    rerank_score_threshold: float = 0.3

    # --- HYDE ---
    hyde_enabled: bool = True
    hyde_max_tokens: int = 256

    # --- Conversation memory ---
    history_window: int = 4  # last N (user, assistant) turns kept

    # --- Logging ---
    log_level: str = "WARNING"


settings = Settings()