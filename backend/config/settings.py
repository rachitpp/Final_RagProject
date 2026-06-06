# =============================================================
# Central configuration.
# Edit values here; no other module hardcodes settings.
# =============================================================
import os
from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class Settings:
    # --- Paths ---
    pdf_path: str = "pdf"  # file OR folder of PDFs
    employee_xlsx_path: str = "data/Copy of Team.xlsx"  # roster imported into users table

    # --- Auth / database ---
    # SQLite file next to the roster it's imported from. Relative path resolves
    # because the backend is always run from inside backend/ (see backend/CLAUDE.md).
    # Overridable via DATABASE_URL (12-factor) — tests point it at a temp file,
    # and it's the one-line swap to Postgres later.
    database_url: str = field(
        default_factory=lambda: os.environ.get("DATABASE_URL", "sqlite:///data/app.db")
    )

    # --- Auth / JWT ---
    # The signing secret is a credential, never a hardcoded default — it's read
    # from the JWT_SECRET env var (loaded from .env by main.py before this module
    # is first imported). Empty here means "must be provided"; token creation
    # raises loudly if it's still empty (see api/security.py).
    jwt_secret: str = field(default_factory=lambda: os.environ.get("JWT_SECRET", ""))
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12  # 12h sessions

    # Brute-force throttle on the auth endpoints: at most N attempts per window
    # per (client IP + employee_id). In-memory / single-process (see api/ratelimit.py).
    login_rate_max_attempts: int = 5
    login_rate_window_seconds: int = 60

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
    # The corpus is tiny (~15 chunks). BM25 (keyword) + vector (semantic)
    # similarity, unioned and deduped, gives high recall; the must-have
    # reference tables are then guaranteed by pinning (see retrieval/pinned.py).
    # No reranker: ms-marco-MiniLM scored these tabular chunks ~0.000 and any
    # binding top_n/threshold dropped answer-bearing tables, so it was inert
    # dead weight. Revisit a real reranker (e.g. bge-reranker) only if the
    # corpus grows large enough that feeding most of it stops being viable.
    vector_k: int = 10
    bm25_k: int = 10

    # --- HYDE ---
    # Off: at ~15 chunks BM25+vector already recall almost everything, so the
    # hypothetical-document step added an LLM call per query for ~zero recall
    # gain. The code remains; flip this on if the corpus grows.
    hyde_enabled: bool = False
    hyde_max_tokens: int = 256

    # --- Conversation memory ---
    history_window: int = 4  # last N (user, assistant) turns kept

    # --- Logging ---
    log_level: str = "WARNING"


settings = Settings()