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

## Next milestone — auth + band-aware answers + leave PDF

Login → JWT → server-side band lookup → auto-scope every answer to the user's
band; add the leave policy to the corpus; route across the multi-domain corpus.
**Full decisions in [`docs/AUTH_PERSONALIZATION_DESIGN.md`](docs/AUTH_PERSONALIZATION_DESIGN.md)** — the load-bearing ones:

- **Two stores:** vector DB = policy *knowledge* (searched by meaning); relational
  DB = *identity* (looked up by `employee_id`). **Never embed the Excel/roster** —
  it's a keyed lookup injected into the prompt, not a vector.
- **This is personalization, not access control** — everyone may read every doc;
  the band only picks which row of the rate table to compute. So **no per-chunk
  ACLs.**
- **User provides only `employee_id` + password.** Band/grade are
  **server-authoritative from Excel**, looked up per request; the **JWT carries
  only `sub`** (never the band).
- **Excel → `users` table; import, don't drop-reload** (a rebuild would wipe
  `password_hash`). Band values must match the policy's labels (e.g. `9/10`).
- **Add `bcrypt`/`passlib`** — the one auth dep not yet pinned (PyJWT, SQLAlchemy,
  openpyxl, pandas already are).
- **Registry, not filename-sniffing:** a config manifest tags each PDF with a
  `domain`; **add `domain`, keep `policy`.** Retrieval keys on a *scope*
  (`domestic | foreign | leave`) — fixes the BM25 `if not policy: continue` drop bug.
- **Router = one structured classify call** → `{scopes, trip_type}`; gate
  pinning/calculator/prompt to travel-only scopes.
- **Open question:** the "grade drives leave" split is unverified — confirm against
  the real `.xlsx` + leave PDF before coding.
