# RAG System — Retrieval-Augmented Generation over PDFs

A production-style RAG assistant for a company's **travel-reimbursement
policies** (Domestic / within-India and Foreign / overseas). You drop the policy
PDFs in, ingest them once, and ask questions in natural language — the system
retrieves the relevant policy text and answers with Google Gemini, grounded in
the document and cited to the page.

---

## What it does

- Reads the policy PDFs (text **and** tables) and stores them as searchable
  vectors in Qdrant Cloud.
- For each question: routes it to the right policy, retrieves the relevant
  chunks (keyword + meaning), guarantees the key reference tables are present,
  and has Gemini answer **only** from that context — streamed, with citations.

---

## Pipeline flow (per question)

```
User query
  → Rewrite          resolve follow-ups using conversation history
  → Classify policy  decide Domestic vs Foreign (the single routing decision)
  → Hybrid retrieval  BM25 keyword + vector meaning search, scoped to that policy
  → Pin tables       always inject the city/country classification + active rate table
  → Gemini 2.5 Flash  stream a grounded, cited answer
```

Ingestion (run once via `create_db.py`): **load + clean (table-aware) → split →
embed → store in Qdrant** with a `policy` tag and a payload index for filtering.

---

## Key components

| Component | Technology |
|---|---|
| LLM | Gemini 2.5 Flash via Vertex AI |
| Embeddings | text-embedding-004 via Vertex AI (768-dim) |
| Vector store | Qdrant Cloud |
| Keyword retrieval | BM25 (`rank-bm25`) |
| PDF parsing | pdfplumber (table-aware) |
| Orchestration | LangChain |
| API | FastAPI (`api/`) — streaming `/chat` endpoint |
| Web UI | React + Vite frontend (see `../frontend/`) |
| Tracing | LangSmith |

> There is intentionally **no reranker** — on this small, table-heavy corpus a
> cross-encoder scored the key tables near zero and dropped them, so retrieval
> uses BM25 + vector + guaranteed (“pinned”) reference tables instead.

---

## Project structure

```
.
├── config/
│   └── settings.py          # Central config — all tuneable parameters
├── conversation/
│   ├── memory.py            # Sliding-window conversation memory
│   └── store.py             # Per-conversation memory store (keyed by id)
├── ingestion/
│   ├── loader.py            # Table-aware PDF loading + cleaning (pdfplumber)
│   ├── splitter.py          # Recursive text splitting
│   └── vector_store.py      # Qdrant collection + embedding + policy index
├── retrieval/
│   ├── classify.py          # Trip-type / policy routing (domestic vs foreign)
│   ├── retrievers.py        # BM25 + vector + policy-scoped hybrid retrieval
│   ├── pinned.py            # Guaranteed reference tables (classification + rate)
│   ├── rewrite.py           # Follow-up query rewriting
│   ├── hyde.py              # Hypothetical Document Embeddings (optional, off)
│   └── formatter.py         # Context formatting with page citations
├── llm/
│   ├── models.py            # LLM + embedding model factories
│   └── prompts.py           # Reasoning prompts (no policy data inside)
├── pipelines/
│   ├── ingestion_pipeline.py
│   └── rag_pipeline.py      # Main RAGPipeline class
├── api/                     # FastAPI service (streaming /chat, /reset, /library)
│   ├── main.py              #   app entry — builds the pipeline once (lifespan)
│   ├── deps.py              #   shared dependencies
│   ├── schemas.py           #   request/response models
│   └── routes/             #   chat, health, meta endpoints
├── utils/
│   └── logger.py
├── main.py                  # Interactive CLI query loop
├── create_db.py             # Run once to ingest PDFs into Qdrant
├── eval.py                  # Evaluation harness
└── requirements.txt
```

---

## Documentation

| Doc | What's in it |
|---|---|
| **[SETUP.md](SETUP.md)** | venv, pip, packages, credentials, running the app |
| **[PIPELINE.md](PIPELINE.md)** | Every ingestion & query step, with file references |
| **[OVERVIEW.md](OVERVIEW.md)** | What the project is and the techniques behind it |

---

## Requirements

- Python 3.10+ (developed on 3.13)
- A Google Cloud project with Vertex AI enabled + a service-account JSON key
- A Qdrant Cloud cluster and API key

See **[SETUP.md](SETUP.md)** to get running.
