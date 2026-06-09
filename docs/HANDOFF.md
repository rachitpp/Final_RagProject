# Session Handoff — Auth + Band-Aware Answers

> ⚠️ **SUPERSEDED — historical.** This plan described auth ("Piece A") as *not
> started*. Auth is now fully built, hardened, and tested. For current status see
> [`PROGRESS.md`](PROGRESS.md); this file is kept only for historical context.

> Written at end of audit session (2026-06-05). Read this before starting
> the next session so you know exactly what's done, what's decided, and
> what to build first.

---

## What was done in this session

1. **Full codebase audit** — read every file in `backend/` and `frontend/`.
2. **Confirmed Piece B is FULLY BUILT** (docs still say "future work" — they're stale).
3. **Confirmed Piece A (auth) is NOT started** — frontend has a UI mockup only.
4. **Inspected the Excel sheet** at `backend/data/Copy of Team.xlsx`.
5. **Made all key decisions** about the Excel schema, database, and login fields.

---

## Audit findings — what's built

### Piece B (registry + leave + router) — DONE ✅
Every item below exists in working code:

- `config/documents.py` — document registry (`filename → scope`, `scope → capabilities`)
- `retrieval/classify.py` — single structured LLM call → `Route{scopes, trip_type, assumed}`;
  handles off-topic (empty scopes → clarify), ambiguous → assumed domestic
- `retrieval/retrievers.py` — per-scope BM25 indexes + scope-filtered vector search;
  `multi_scope_retrieve` unions across scopes; the old `if not policy: continue` BM25 drop bug is fixed
- `ingestion/loader.py` — uses registry (no more filename sniffing); stamps `scope` on every chunk
- `ingestion/vector_store.py` — creates `metadata.scope` payload index (Qdrant strict-mode safe)
- `llm/tools.py` — `compute_entitlement` **AND** `compute_leave_ledger` (accrual, eligibility,
  LWOP, combination rules — well beyond the original spec)
- `llm/prompts.py` — `ANSWER_PROMPT`, `LEAVE_ANSWER_PROMPT`, `LEAVE_ADDENDUM`
- `pipelines/rag_pipeline.py` — capability-gated tool binding; leave-only path uses
  `LEAVE_ANSWER_PROMPT` with no travel machinery

### Piece A (auth + band personalization) — NOT STARTED ❌
- No `/login` or `/activate` route
- No `users` table / SQLAlchemy model
- No `import_employees.py`
- No `get_current_user` FastAPI dependency
- `stream_answer()` takes no `user_profile` argument
- Prompt still answers "for every band" — no band injection
- `requirements.txt` missing `bcrypt`/`passlib` (flagged in design doc; everything else already pinned)

### Frontend auth — UI mockup only 🟡
- `AuthPage.tsx` explicitly says "PRESENTATIONAL MOCKUP ONLY — Submit is a no-op stub"
- `api.ts` sends **no `Authorization: Bearer` header**
- `ChatPage` (route `/`) has **no auth guard** — currently anyone can skip login and chat anonymously
- The router (`main.tsx`) has `/login` and `/activate` routes wired to `AuthPage` — routing is done,
  the wiring to real endpoints is not

---

## Key decisions made this session

### Excel sheet (`backend/data/Copy of Team.xlsx`)

**Current state (wrong):**
- `Grade` column contains `A / B / C` — these are *city categories* (a property of destinations),
  NOT employee bands. If used as-is, the band lookup will silently fail.
- `Leave Taken` column — unused by the code, ambiguous (doesn't say PL/SL/CL), should be dropped.
- Missing `Email` column — required for activation identity verification.
- Missing `Date of Joining` — needed for leave accrual (parked for now, but add it).

**Required schema:**
| Column | Notes |
|---|---|
| Employee ID | keep as-is (`E101` format) — login key |
| Employee Name | keep |
| Email | **ADD** — work email; matched at activation to verify identity |
| Band | **FIX** — must be a **number 1–10**, NOT a letter (A/B/C). The policy rate tables are keyed on bands like `9/10`, `7/8` etc.; storing a single number lets both domestic and foreign groupings be resolved correctly. |
| Date of Joining | **ADD** — `YYYY-MM-DD`; needed for leave accrual later |
| ~~Leave Taken~~ | **DROP** — unused and ambiguous |

Band values for dummy data: use actual numbers 1–10 spread across the 8 employees.
Example spread: 9, 7, 8, 4, 10, 6, 3, 7 (exercises all tier groups + the domestic/foreign 7-vs-8 split).

### Database: SQLite via SQLAlchemy
- **Location:** `backend/data/app.db` — next to the Excel it's imported from
- **Setting:** add `database_url: str = "sqlite:///data/app.db"` to `config/settings.py`
- **Why SQLite:** it's a file, zero infrastructure, SQLAlchemy already pinned, correct for an internal tool.
  Postgres/pgvector is a one-URL-line upgrade later if needed; we won't hit the trigger.
- **⚠️ Gitignore:** add `*.xlsx`, `*.db`, `/data/` to `backend/.gitignore` — PII + password hashes.

### What the user types at login (and what they never type)
- **Login (returning user):** Employee ID + Password
- **Activate (first time):** Employee ID + Email (must match the roster) + New Password + Confirm
- **Band is NEVER typed by the user.** After login the server reads band from the DB by Employee ID
  and injects it into the prompt. If the user could type their band, personalization would be spoofable.

---

## Build order for next session

Steps 1–3 are one-time setup (no auth logic yet).
Steps 4–8 are the auth backend.
Steps 9–10 are the frontend wiring.
Steps 1–3 and 4–8 should land in order; 9–10 follow after the backend is up.

### Step 1 — Fix the Excel sheet
Update `backend/data/Copy of Team.xlsx`:
- Rename `Grade` → `Band`, change values to numbers 1–10
- Add `Email` column
- Add `Date of Joining` column
- Drop `Leave Taken` column

### Step 2 — Gitignore + settings
- `backend/.gitignore`: add `*.xlsx`, `*.db`, `*.sqlite3`, `/data/`
- `config/settings.py`: add `database_url` and `employee_xlsx_path`

### Step 3 — SQLAlchemy `users` table model
New file `backend/db/models.py`:
- `User` table: `employee_id` PK, `name`, `email` UNIQUE, `band`, `date_of_joining`,
  `password_hash` (nullable until activation), `activated_at`, `role`, `created_at`, `updated_at`
- `backend/db/session.py`: `engine` + `SessionLocal` + `get_db` dependency
- `backend/db/base.py`: `Base = declarative_base()`

### Step 4 — `import_employees.py`
`backend/import_employees.py`:
- reads `settings.employee_xlsx_path` with pandas/openpyxl
- validates: required columns present, band is numeric 1–10, no duplicate employee_id
- **UPSERT** by `employee_id` (update roster fields; never touch `password_hash` or `activated_at`)
- creates the table if it doesn't exist; never drops it

### Step 5 — `bcrypt`/`passlib` dependency
Add `passlib[bcrypt]` to `requirements.txt`.

### Step 6 — Auth routes
New file `backend/api/routes/auth.py`:
- `POST /activate` — verify Employee ID exists + email matches → set bcrypt password hash
- `POST /login` — verify password → issue JWT `{ sub: employee_id }` (PyJWT, already pinned)
- Add `JWT_SECRET` (and `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`) to `config/settings.py` backed by
  env var via `pydantic-settings` (already pinned)
- Wire into `api/main.py`

### Step 7 — `get_current_user` dependency
In `backend/api/deps.py`:
- decode JWT → `employee_id` (401 if invalid/expired)
- `SELECT band, name FROM users WHERE employee_id = sub` → `UserProfile`
- Add `UserProfile` dataclass to `api/schemas.py`

### Step 8 — Band injection into the pipeline
- `stream_answer(query, history, user_profile=None)` — add optional `user_profile` arg
- When `user_profile` is present and a travel scope is active: inject `{employee_context: band}`
  into `ANSWER_PROMPT` instead of answering for every band
- Update `ANSWER_PROMPT` in `llm/prompts.py`: add an `{employee_context}` block that activates
  when band is known and suppresses the "answer for every band" fallback
- Update `api/routes/chat.py` to pass `Depends(get_current_user)` and forward `user_profile`
- Scope `conversation_id` to `sub` server-side (security gap: anyone can pass another's id today)

### Step 9 — Frontend: wire AuthPage to real endpoints
In `frontend/src/lib/api.ts`:
- Add `login(employeeId, password)` → `POST /login` → stores JWT in `localStorage`
- Add `activate(employeeId, email, password)` → `POST /activate`
- Add `logout()` → clears token

In `frontend/src/hooks/useAuth.ts` (new):
- `isAuthenticated`, `login`, `logout`, `activate`
- reads/writes token from `localStorage`

Wire `AuthPage.tsx` form submit to these calls (remove the no-op stub).

### Step 10 — Frontend: auth guard + attach JWT
- `ChatPage` route: redirect to `/login` if not authenticated
- `api.ts` `streamChat()`: add `Authorization: Bearer <token>` header
- Handle 401 responses: clear token, redirect to `/login`

---

## Other open items (lower priority)

- **Eval harness** (`eval.py`) covers only travel (22 cases). Leave/router/cross-scope paths
  have no regression guard — add gold cases after auth lands.
- **Source PDFs** are not in the repo (gitignored, `*.pdf`). Qdrant Cloud is already populated,
  but `create_db.py` can't re-ingest from a fresh clone without them. Keep them somewhere safe.
- **Documentation drift** — `docs/ROADMAP.md` and `docs/AUTH_PERSONALIZATION_DESIGN.md` still say
  Piece B is future work; they're now stale. Low priority but worth a quick update.
- **`api/main.py` docstring** says `Project_123.json` (underscore) — real file is `Project-123.json` (hyphen).
