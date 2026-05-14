# RAG System — Retrieval-Augmented Generation over PDFs

A production-style RAG pipeline that lets you chat with your PDF documents using Google Gemini and Qdrant Cloud as the vector store.

---

## What it does

You drop in a PDF, run the ingestion script once, and then ask questions in natural language. The system retrieves the most relevant chunks from the document and uses Gemini to generate a grounded, cited answer.

---

## Pipeline flow

```
User query
    → Query Rewrite      (resolves follow-ups using conversation history)
    → HYDE               (generates a hypothetical answer passage for better vector search)
    → Hybrid Retrieval   (BM25 keyword search + Vector MMR search in parallel)
    → Cross-Encoder Rerank + Confidence Filter
    → Gemini 2.5 Flash   (streams the final answer token by token)
```

---

## Key components

| Component | Technology |
|---|---|
| LLM | Gemini 2.5 Flash via Vertex AI |
| Embeddings | text-embedding-004 via Vertex AI |
| Vector Store | Qdrant Cloud |
| Sparse Retrieval | BM25 (rank-bm25) |
| Reranker | cross-encoder/ms-marco-MiniLM-L-6-v2 |
| Orchestration | LangChain |
| Tracing | LangSmith |

---

## Project structure

```
.
├── config/
│   └── settings.py          # Central config — all tuneable parameters
├── conversation/
│   └── memory.py            # Sliding-window conversation memory
├── ingestion/
│   ├── loader.py            # PDF loading (pypdf)
│   ├── splitter.py          # Recursive text splitting
│   └── vector_store.py      # Qdrant collection creation + embedding
├── llm/
│   ├── models.py            # LLM + embedding model factories
│   └── prompts.py           # Prompt templates
├── pipelines/
│   ├── ingestion_pipeline.py
│   └── rag_pipeline.py      # Main RAG pipeline class
├── retrieval/
│   ├── formatter.py         # Context formatting
│   ├── hyde.py              # Hypothetical Document Embedding
│   ├── reranker.py          # Cross-encoder reranking
│   ├── retrievers.py        # BM25 + vector + hybrid retrieval
│   └── rewrite.py           # Query rewriting
├── utils/
│   └── logger.py
├── create_db.py             # Run once to ingest PDF into Qdrant
├── main.py                  # Interactive query loop
└── requirements.txt
```

---

## Requirements

- Python 3.11+
- A Google Cloud project with Vertex AI enabled and a service account JSON key
- A Qdrant Cloud cluster and API key
