# CLAUDE.md

RAG assistant for company **travel-reimbursement policies** (Domestic / Foreign).
Two independently-runnable apps: a FastAPI + LangChain backend and a React + Vite
frontend. Policy PDFs are ingested into Qdrant; users ask questions and get
grounded, page-cited answers streamed from Gemini.

- `backend/` — FastAPI API + RAG pipeline. See [`backend/CLAUDE.md`](backend/CLAUDE.md).
- `frontend/` — React chat UI. See [`frontend/CLAUDE.md`](frontend/CLAUDE.md).

## Project-wide rules

- **Math stays in code, not the model.** Totals go through the
  `compute_entitlement` tool (`backend/llm/tools.py`). Never bake rates into prompts.
- **Policy data stays in the PDFs / retrieved context** — never hardcode policy
  rates or rules in `llm/prompts.py`.
- **All tunables live in `backend/config/settings.py`** — don't hardcode model
  names, chunk sizes, retrieval `k`s, or the Qdrant URL elsewhere.
- **Policy routing is decided once** in `classify_trip_type()` — consume that
  decision, don't re-derive it.
- **The pipeline is stateless per conversation** — history lives in the caller's
  store, never on the pipeline.
- **Windows: install from `backend/requirements_win.txt`** (drops `uvloop`,
  which doesn't build on Windows; uvicorn runs fine without it).

## Run it (two terminals)

```bash
# backend → http://localhost:8000
cd backend && venv\Scripts\python -m uvicorn api.main:app --reload --port 8000

# frontend → http://localhost:5173
cd frontend && npm run dev
```

Ingest once: `cd backend && venv\Scripts\python create_db.py`.
Credentials in `backend/.env`. Full setup: [`INSTALL.md`](INSTALL.md), `backend/SETUP.md`.

## Deeper docs (read on demand)

- [`docs/OVERVIEW.md`](docs/OVERVIEW.md) — full pipeline walkthrough, how the
  two halves connect, file-by-file map.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — the next major milestone.
- [`docs/AUTH_PERSONALIZATION_DESIGN.md`](docs/AUTH_PERSONALIZATION_DESIGN.md) —
  agreed design decisions for the next milestone (auth, band-aware answers, leave
  PDF, the router). Read this before building any of it.

## Current milestone — auth + band-aware answers

> **Piece B (leave PDF + multi-domain router) is DONE.** The registry, scopes,
> per-scope BM25, structured router, `compute_leave_ledger`, leave prompts — all
> built and working. The docs that called this "future work" are stale.
>
> **Piece A (auth + band injection) is what remains.** Full session notes and
> step-by-step build order in [`docs/HANDOFF.md`](docs/HANDOFF.md) — read that
> before starting work.

### What's left to build (Piece A only)

Login → JWT → server-side band lookup → auto-scope every travel answer to the
user's band. The app currently answers "for every band" because it has no idea
who is asking. Auth fixes that.

**Decisions already locked:**

- **Excel sheet** at `backend/data/` — `Band` column must be a number **1–10**
  (NOT letter grades). `Email` and `Date of Joining` columns are required.
  See [`docs/HANDOFF.md`](docs/HANDOFF.md) for the full schema.
- **Database: SQLite** (`backend/data/app.db`) via SQLAlchemy (already pinned).
  Setting: `database_url` in `config/settings.py`.
- **User provides only `employee_id` + password at login.** Band is
  **server-authoritative** — looked up from SQLite per request, never typed.
  JWT carries only `sub` (never the band).
- **Excel → `users` table via upsert** — never drop-reload (would wipe
  `password_hash`).
- **Add `passlib[bcrypt]`** — the one auth dep not yet in `requirements.txt`.
- **Full design decisions** in [`docs/AUTH_PERSONALIZATION_DESIGN.md`](docs/AUTH_PERSONALIZATION_DESIGN.md).
