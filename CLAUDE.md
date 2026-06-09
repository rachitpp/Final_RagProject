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
- **One `requirements.txt` for all platforms** — `uvloop` carries a
  `platform_system != "Windows"` marker (it doesn't build on Windows; uvicorn
  runs fine without it), so `pip install -r requirements.txt` just works everywhere.

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

- [`docs/PROGRESS.md`](docs/PROGRESS.md) — **current status**: what's built,
  hardened, and verified. Start here.
- [`docs/OVERVIEW.md`](docs/OVERVIEW.md) — full pipeline walkthrough, how the
  two halves connect, file-by-file map (predates auth/leave — see PROGRESS).
- [`docs/AUTH_PERSONALIZATION_DESIGN.md`](docs/AUTH_PERSONALIZATION_DESIGN.md) —
  design decisions behind auth + band-aware answers (now implemented).
- [`docs/ROADMAP.md`](docs/ROADMAP.md) · [`docs/HANDOFF.md`](docs/HANDOFF.md) —
  historical planning notes for the auth milestone (delivered; kept for context).

## Status — auth + band-aware answers (SHIPPED)

Both milestones are built, hardened, and tested (backend `pytest` green):

- **Piece B** — leave PDF + multi-domain router: registry, scopes, per-scope
  BM25, structured router, `compute_leave_ledger`, leave prompts.
- **Piece A** — auth + band injection: login/activation, JWT (carries only
  `sub`), server-authoritative band lookup, band-scoped travel answers, and
  per-user conversation isolation. The Excel roster imports into a SQLite
  `users` table via upsert; `passlib[bcrypt]` is pinned.

See [`docs/PROGRESS.md`](docs/PROGRESS.md) for the full build log and the
consciously-deferred items (Alembic, Redis/multi-process, JWT revocation).
