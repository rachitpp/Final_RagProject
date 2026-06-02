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
    # The band rate matrix renders to ~1.1k chars as one self-describing table
    # (loader stitches it back together across the PDF page break). A 1000-char
    # window would re-split it mid-table, undoing that work — so the window is
    # sized to keep a whole table in one chunk while still splitting the larger
    # prose pages.
    chunk_size: int = 1500
    # Splits land mostly on "\n\n" part boundaries (narrative vs table), so a
    # large overlap mostly just duplicates text across adjacent chunks (both of
    # which are usually retrieved on this small corpus). Keep it small.
    chunk_overlap: int = 80
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
    # The corpus is tiny (~15 chunks). Policy-scoped vector (semantic)
    # similarity with k=10 already recalls almost the entire policy sub-corpus;
    # the must-have reference tables are then guaranteed by pinning (see
    # retrieval/pinned.py). An A/B run of the eval harness showed BM25 (hybrid)
    # and HYDE added zero answer-quality gain at this size, so neither is used.
    # Revisit hybrid search / a reranker only if the corpus grows large enough
    # that feeding most of it to the model stops being viable.
    vector_k: int = 10

    # --- Conversation memory ---
    history_window: int = 4  # last N (user, assistant) turns kept

    # --- Logging ---
    log_level: str = "WARNING"


settings = Settings()