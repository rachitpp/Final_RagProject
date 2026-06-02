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
  chunks (semantic search), guarantees the key reference tables are present,
  and has Gemini answer **only** from that context — streamed, with citations.

---

## Pipeline flow (per question)

```
User query
  → Rewrite          resolve follow-ups using conversation history
  → Classify policy  decide Domestic vs Foreign (the single routing decision)
  → Vector retrieval  semantic (meaning) search, scoped to that policy
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
| PDF parsing | pdfplumber (table-aware) |
| Orchestration | LangChain |
| UI | Streamlit (`app.py`) |
| Tracing | LangSmith |

> Retrieval is deliberately kept simple: **policy-scoped vector search +
> guaranteed (“pinned”) reference tables.** On this small, table-heavy corpus
> an A/B run of the eval harness showed that hybrid (BM25) search, HYDE
> query-expansion, and a cross-encoder reranker all added no answer-quality
> gain — the reranker actively dropped the key tables — so none are used.

---

## Project structure

```
.
├── config/
│   └── settings.py          # Central config — all tuneable parameters
├── conversation/
│   └── memory.py            # Sliding-window conversation memory
├── ingestion/
│   ├── loader.py            # Table-aware PDF loading + cleaning (pdfplumber)
│   ├── splitter.py          # Recursive text splitting
│   └── vector_store.py      # Qdrant collection + embedding + policy index
├── retrieval/
│   ├── classify.py          # Trip-type / policy routing (domestic vs foreign)
│   ├── retrievers.py        # Policy-scoped vector (semantic) search
│   ├── pinned.py            # Guaranteed reference tables (classification + rate)
│   ├── rewrite.py           # Follow-up query rewriting
│   └── formatter.py         # Context formatting with page citations
├── llm/
│   ├── models.py            # LLM + embedding model factories
│   └── prompts.py           # Reasoning prompts (no policy data inside)
├── pipelines/
│   ├── ingestion_pipeline.py
│   └── rag_pipeline.py      # Main RAGPipeline class
├── ui/                      # Streamlit UI (render, sidebar, behaviours)
├── styles/                  # UI CSS
├── utils/
│   └── logger.py
├── app.py                   # Streamlit web app
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
