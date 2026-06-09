# backend/CLAUDE.md

FastAPI service wrapping a LangChain RAG pipeline over travel-policy PDFs.
For the project-wide rules and run commands see the root [`CLAUDE.md`](../CLAUDE.md);
for the full narrative see [`../docs/OVERVIEW.md`](../docs/OVERVIEW.md).

## Layout

- `api/` — FastAPI app. `main.py` builds the pipeline once in a `lifespan` hook
  and sets CORS for the Vite origin. Routes: `chat` (`POST /chat` streams plain
  text, `POST /reset`), `meta` (`GET /library`), `health`. Models in `schemas.py`.
- `pipelines/rag_pipeline.py` — the `RAGPipeline` class (built once, reused).
- `retrieval/` — `rewrite`, `classify`, `retrievers` (BM25 + vector), `pinned`
  (guaranteed reference tables), `formatter`, `hyde` (off).
- `ingestion/` — `loader` (table-aware pdfplumber), `splitter`, `vector_store`.
- `llm/` — `models` (Gemini/Vertex factories), `prompts`, `tools`
  (`compute_entitlement`).
- `conversation/` — `store.py` (per-`conversation_id` memory) + `memory.py`.
- `config/settings.py` — central frozen config.
- `main.py` — CLI loop · `create_db.py` — one-time ingest · `eval.py` — eval harness.

The web UI is the **React app in `../frontend/`** talking to the FastAPI service;
there is no server-rendered UI in the backend.

## Backend-specific rules

- **Math in code:** any rate×days / multi-leg total goes through
  `compute_entitlement` (`llm/tools.py`). The model extracts figures from
  retrieved tables; the tool sums them.
- **Policy routing once:** `classify_trip_type()` (`retrieval/classify.py`) is
  the single source of truth — it drives the body filter, which rate table is
  pinned, and the prompt's grounding line. Default to Domestic when ambiguous.
- **Pin, don't rerank.** No reranker (it scored the tabular chunks ~0 and
  dropped them); recall comes from BM25 + vector + pinned reference tables.
- **Stateless pipeline:** never store chat history on `RAGPipeline`; the caller
  (`conversation/store.py` for the API, `main.py` for CLI) owns it.
- **All tunables in `config/settings.py`** — no hardcoded model names / k's / URLs.
- **Prompts hold no policy data** (`llm/prompts.py`) — rates come from context.

## Gotchas

- **Run from inside `backend/`** so relative paths (`.env`, service-account JSON)
  resolve.
- **Install:** `pip install -r requirements.txt` on every platform — `uvloop` is
  marked `platform_system != "Windows"` (it won't build on Windows; uvicorn runs
  without it). Create the venv with `python -m venv venv`, then call
  `venv\Scripts\python` explicitly.
- Needs `backend/.env` with Vertex service-account creds + Qdrant API key.
- Memory is in-process (single-process demo); swap `ConversationStore` for
  Redis/DB for persistence or multi-process.
