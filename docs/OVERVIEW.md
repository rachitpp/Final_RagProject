# Project Overview

Full narrative for the travel-reimbursement RAG assistant. For the terse rules
Claude loads every session see [`../CLAUDE.md`](../CLAUDE.md),
[`../backend/CLAUDE.md`](../backend/CLAUDE.md), and
[`../frontend/CLAUDE.md`](../frontend/CLAUDE.md).

> ℹ️ **Partly out of date.** This narrative predates the auth layer and the
> multi-domain (leave) router. For current, accurate status — auth, band-aware
> answers, the leave scope — see [`PROGRESS.md`](PROGRESS.md).

---

## What this project is

A production-style **RAG (Retrieval-Augmented Generation) assistant** for a
company's **travel-reimbursement policies** — Domestic (within India) and
Foreign (overseas). Policy PDFs are ingested once into a vector store; users
then ask questions in natural language and get **grounded, page-cited answers**
streamed back from Google Gemini.

| Folder | Stack | Role |
|---|---|---|
| `backend/` | FastAPI + LangChain + Qdrant + Vertex AI (Gemini) | RAG pipeline + streaming API |
| `frontend/` | React 19 + Vite + TypeScript + Tailwind v4 | Chat UI that streams answers |

The user-facing experience is the **React frontend talking to the FastAPI
backend**: the frontend streams answers from the API's `/chat` endpoint.

---

## Backend — what's done

### The RAG pipeline (`pipelines/rag_pipeline.py`)
One `RAGPipeline` class, built **once** at startup and reused (stateless per
conversation). Per-question flow:

```
User query
  → Rewrite          resolve follow-ups using conversation history   (retrieval/rewrite.py)
  → Classify policy  decide Domestic vs Foreign — the single routing decision  (retrieval/classify.py)
  → Hybrid retrieval BM25 keyword + vector meaning search, scoped to that policy  (retrieval/retrievers.py)
  → Pin tables       always inject the city/country classification + active rate table  (retrieval/pinned.py)
  → Gemini 2.5 Flash stream a grounded, cited answer  (llm/)
```

Key design decisions already baked in:
- **Policy isolation lives in retrieval, not the prompt.** Trip type is decided
  once in `classify_trip_type()` and that single decision drives the body
  filter, which rate table gets pinned, and the prompt's grounding line — so
  they can never disagree. Conservative default: Domestic when ambiguous.
- **Arithmetic is owned by code, not the model.** `llm/tools.py` exposes a
  `compute_entitlement` tool the LLM is forced to call for any rate×days /
  multi-leg total. The model extracts figures from the retrieved policy tables;
  the tool sums them exactly. (Fixes observed LLM math slips like
  ₹4000×3 + ₹2500×3 → 21000 instead of 19500.)
- **No reranker.** On this small, table-heavy corpus (~15 chunks) a
  cross-encoder scored the key tables near zero and dropped them. BM25 + vector
  + *pinned* reference tables is used instead. (See `config/settings.py` notes.)
- **HYDE is implemented but off** — negligible recall gain at this corpus size.

### Ingestion (`ingestion/`, `create_db.py`, `pipelines/ingestion_pipeline.py`)
Run once: **load + clean (table-aware via pdfplumber) → split → embed
(text-embedding-004, 768-dim) → store in Qdrant Cloud** with a `policy` payload
index for filtering. Chunk size 1500 to keep whole rate tables intact.

### The FastAPI service (`api/`)
- `api/main.py` — app entry. Builds the heavy pipeline once in a `lifespan`
  hook; configures CORS for the Vite dev origin (`localhost:5173`).
- `api/routes/chat.py` — `POST /chat` streams the answer as plain text
  token-by-token (`StreamingResponse`); `POST /reset` clears a conversation.
- `api/routes/meta.py` — `GET /library` lists indexed docs + active model.
- `api/routes/health.py` — health check.
- `api/schemas.py` — `ChatRequest` / `ResetRequest` Pydantic models.
- `conversation/store.py` + `conversation/memory.py` — **per-`conversation_id`
  in-memory** sliding-window memory (last 4 turns). Swappable for Redis/DB later.

### Config & support
- `config/settings.py` — central, frozen config; no other module hardcodes tunables.
- `llm/models.py` — LLM + embedding factories (Gemini / Vertex AI).
- `llm/prompts.py` — reasoning prompts (deliberately contain **no** policy data).
- `main.py` — interactive CLI query loop (alternative to the API).
- `eval.py` — evaluation harness.
- Docs: `backend/README.md`, `backend/SETUP.md`, `backend/PIPELINE.md`, `backend/OVERVIEW.md`.

**Windows note:** a single `requirements.txt` works on all platforms — `uvloop`
carries a `platform_system != "Windows"` marker (it doesn't build on Windows;
uvicorn runs fine without it).

---

## Frontend — what's done

A polished, single-page React chat client (Vite scaffold, React 19, TS,
Tailwind v4, shadcn/ui).

- `src/pages/ChatPage.tsx` — the whole chat screen: composer with auto-growing
  textarea, Enter-to-send / Shift+Enter newline, ChatGPT-style "lift the new
  question to the top so the answer streams in below," click-a-starter-question,
  Stop button while streaming.
- `src/hooks/useChatStream.ts` — owns chat state. Appends a user turn + an empty
  assistant turn, then fills it as tokens arrive. Persists a `conversation_id` in
  `localStorage` (survives refresh). Handles Stop (keeps partial text) and hard
  failures (removes the broken turn, offers a Retry toast).
- `src/lib/api.ts` — `streamChat()` reads the `POST /chat` response body as a
  stream and yields text chunks; `resetConversation()` hits `/reset`;
  `fetchLibrary()` hits `/library`. API base from `VITE_API_BASE`.
- Components: `Sidebar`, `Welcome` (starter questions), `ChatMessage`,
  `Markdown` (react-markdown + remark-gfm for tables), `ThinkingIndicator`,
  `components/ui/button`.
- `src/hooks/useTheme.ts` — light/dark toggle. Toasts via `sonner`.
- Path alias `@` → `src/` (`vite.config.ts`).

`frontend/README.md` is still the **default Vite template** — not customized.

---

## How the two halves connect

```
React (5173)  ──POST /chat {question, conversation_id}──▶  FastAPI (8000)
     ▲                                                          │
     └──────────  streamed plain-text answer tokens  ◀──────────┘
```

Memory is keyed by a client-generated `conversation_id` (localStorage) sent on
every call; the backend looks up that conversation's history, uses it only to
rewrite follow-ups, and appends the completed turn after the stream finishes.

---

## Running it (two terminals)

```bash
# Terminal 1 — backend → http://localhost:8000
cd backend
# Windows: python -m venv venv  then  venv\Scripts\python -m pip install -r requirements.txt
venv\Scripts\python -m uvicorn api.main:app --reload --port 8000

# Terminal 2 — frontend → http://localhost:5173
cd frontend
npm install     # requires Node.js 18+ installed and on PATH
npm run dev
```

Ingestion (once, to populate Qdrant): `venv\Scripts\python create_db.py`.
Credentials live in `backend/.env`. See `INSTALL.md` and `backend/SETUP.md`.
