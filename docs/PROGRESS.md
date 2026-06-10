# Session Progress — Auth, Hardening & UI Personalization

> Written 2026-06-06. This captures everything built **after** the original
> `docs/HANDOFF.md` (which is now stale — it described "Piece A" as *not started*;
> Piece A is now fully built, hardened, tested, and given a personalized UI).
>
> Read this before continuing. **Nothing in this session is committed yet.**

---

## TL;DR — where the project stands

- **Piece A (auth + band-aware answers) is DONE** — login/activation, JWT,
  server-authoritative band, band-scoped travel answers, per-user conversation
  isolation.
- **It was then hardened** to industry standard (tests, rate limiting, timing
  fix, fail-fast secret, audit logging, shared auth store, …).
- **A personalized + responsive UI was added** — the chat shows who's signed in
  (name · ID · band) with a sign-out menu, a personalized welcome, a
  registry-driven "Policies" list, a full mobile shell (slide-in drawer + top
  bar), and accessibility/polish passes.
- **Verification is green:** backend `32 passed`; frontend `tsc` + `eslint`
  (--max-warnings 0) + `vite build` all clean.
- **Deploy-hardening (2026-06-10):** two abuse/stability holes closed — see below.

---

## Deploy-hardening pass (2026-06-10)

Two contained changes toward deployability; both tested (`32 passed`):

1. **Per-user rate limit on `/chat`** — every call hits paid Gemini, so a
   `chat_limiter` (reusing `SlidingWindowLimiter`, keyed by `employee_id`, not
   IP) now returns 429 + `Retry-After` before any paid work. Tunables:
   `chat_rate_max_requests` / `chat_rate_window_seconds` (20/min) in settings.
2. **`ConversationStore` is bounded** — was an unbounded dict (slow memory
   leak / DoS vector). Now an `OrderedDict` LRU capped at
   `conversation_max_sessions` (1000) with a `conversation_ttl_seconds` (2h)
   idle expiry, swept lazily on access (O(expired), not O(all)). Eviction only
   forgets follow-up context; the conversation just restarts with empty memory.

Still open for a real deployment: TLS + production `CORS_ALLOW_ORIGINS` +
strong `JWT_SECRET` (config, not code), outbound timeouts on Vertex/Qdrant,
deeper `/health`.

---

## What was built this session (3 phases)

### Phase 1 — Build Piece A (auth + band injection), the 10-step plan
1. **Excel roster fixed** (`backend/data/Copy of Team.xlsx`): `Grade` (A/B/C city
   categories — wrong) → numeric **`Band` 1–10**; added **`Email`** + **`Date of
   Joining`**; dropped `Leave Taken`. 8 employees, bands `9,7,8,4,10,6,3,7`.
2. **Gitignore + settings**: `.gitignore` adds `*.xlsx,*.db,*.sqlite3,/data/`;
   `settings.py` gains `employee_xlsx_path` + `database_url`. The PII xlsx was
   `git rm --cached`'d (history was clean — emails were only added this session).
3. **SQLAlchemy `db/` package**: `base.py` (DeclarativeBase), `models.py`
   (`User`), `session.py` (`engine`/`SessionLocal`/`get_db`/`init_db`).
4. **`import_employees.py`**: validates (cols present, band int 1–10, no dup
   id/email) then **UPSERTs by employee_id** — never wipes `password_hash` /
   `activated_at` (verified). Re-runnable.
5. **Deps**: pinned `passlib[bcrypt]==1.7.4` + `bcrypt==4.0.1` (the lower bcrypt
   dodges the passlib version-read warning).
6. **Auth routes** (`api/routes/auth.py`): `POST /auth/activate`, `POST /auth/login`
   (issues JWT `{sub}`). `api/security.py` holds password + JWT helpers. JWT
   settings in `settings.py` (secret from `JWT_SECRET` env).
7. **`get_current_user`** (`api/deps.py`): decode JWT → DB lookup →
   `UserProfile`. **Band is read from the DB per request, never from the token.**
8. **Band injection**: `stream_answer(..., user_profile)` + `EMPLOYEE_BAND_CONTEXT`
   in `ANSWER_PROMPT` (answer for the user's band only, suppress the all-bands
   table). Chat route now requires auth and namespaces memory as
   `"{employee_id}:{conversation_id}"`.
9. **Frontend auth**: `api.ts` `login`/`activate`/`logout`; `useAuth`; `AuthPage`
   wired to real endpoints.
10. **Frontend guards**: `RequireAuth`/`RequireAnon`, `Authorization: Bearer`
    header on chat, 401 → clear token + redirect, sign-out button.

### Phase 2 — Audit & hardening (after a code-quality review)
- **JWT fail-fast** at startup: refuse to boot if `JWT_SECRET` is missing or
  `< 32` chars (`api/main.py`).
- **Login timing oracle closed**: `dummy_verify()` runs a bcrypt check on the
  no-such-user path so timing can't reveal which accounts exist.
- **Email normalized** to lowercase on import + activation.
- **Rate limiting** (`api/ratelimit.py`): in-memory sliding window, per
  (IP, employee_id), `429 + Retry-After`, on `/auth/login` + `/auth/activate`.
  Tunables in `settings.py`. (Single-process/demo-grade — see Deferred.)
- **Audit logging**: login/activation success+failure (id + IP, never passwords).
- **Cleanups**: `RosterValidationError` rename; `UserContext` Protocol typing for
  `user_profile`; dropped redundant `future=True`; docstring typo fix.
- **Tests**: `backend/tests/` (pytest) — `test_auth.py`, `test_import.py`,
  `test_chat.py` + `conftest.py` (isolated temp SQLite via `DATABASE_URL`).
  `requirements-dev.txt` added (pytest kept out of the runtime freeze).
  `database_url` is now env-overridable (12-factor / one-line Postgres swap).
- **Shared auth store**: `useAuth` per-component state → `AuthProvider` (React
  Context) single source of truth + cross-tab `storage` sync. localStorage-vs-
  cookie tradeoff documented in `api.ts`.
- **Connection hold fixed**: `get_current_user` uses a short-lived session
  (releases the DB connection instead of pinning it for the whole `/chat` stream).

### Phase 3 — UI: personalization, registry-driven library, responsive shell

**Personalization**
- **`GET /auth/me`** (`ProfileResponse`) returns the signed-in user's
  `{employee_id, name, band, role}`.
- Frontend fetches it on login → cached in `AuthProvider` (`profile`); cleared on
  logout; a 401 from it signs out cleanly.
- **Sidebar identity block + account menu**: avatar (initials) + name +
  "E101 · Band 9"; the whole block is a Radix `DropdownMenu` trigger → **Sign out**.
- **Personalized welcome**: "Welcome back, {firstName}." with first-person starter
  prompts ("What's my lodging allowance…"). The band itself surfaces in the
  sidebar identity block and in the *answers* (band-scoped) — there's no separate
  "band chip" in the welcome.

**Registry-driven Policies list** (replaces raw filenames)
- The sidebar's **Policies** section lists docs from `GET /library` using the
  backend registry's **employee-facing titles** (`title`) and a `topic` key —
  never raw filenames. `topic → icon`: domestic = `Plane`, foreign = `Globe`,
  leave = `CalendarDays`, fallback `FileText`. Load error → inline **Retry**;
  active model shown in the status line.
- Backed by `config/documents.py` (`SCOPE_TITLES`, `title_for`, `topic_for`) +
  the meta route — add a PDF to the registry and it shows up titled + iconed, no
  frontend change.

**Responsive shell (mobile)**
- `Sidebar` split into **`SidebarContent`** (shared chrome) + **`Sidebar`** (fixed
  desktop rail, hidden below `md`).
- Mobile: a Radix **`Dialog` slide-in drawer** (focus trap, Escape, scroll lock)
  reusing `SidebarContent`, plus a **mobile top bar** (hamburger + brand + New
  chat). `onNavigate` dismisses the drawer after New chat.
- Adopted **`radix-ui`** (`DropdownMenu` + `Dialog`); **removed the shadcn
  `components/ui/button`** in favor of plain Tailwind buttons (the only consumer
  was auth, now bespoke).

**Accessibility & polish**
- A single **polite live region** announces stream start/finish **once** (instead
  of re-announcing the whole growing bubble every token); icon buttons carry
  `aria-label`s; JS-driven scrolls honor `prefers-reduced-motion`.
- **`ThinkingIndicator`**: breathing ◐ glyph + rotating pipeline-stage captions
  ("Embedding query" → "Retrieving passages" → "Reading sources") until the first
  token.
- **Brand identity**: "◐ Policy Assistant — Travel & leave, answered for you.";
  ambient ◐ watermark; `AuthPage` theme toggle + smooth login↔activate height-morph.

---

## How to run + test

```bash
# backend  → http://localhost:8000
cd backend && venv/bin/python -m uvicorn api.main:app --reload --port 8000
# frontend → http://localhost:5173
cd frontend && npm run dev

# tests
cd backend && venv/bin/python -m pytest tests/ -q          # 27 passing
cd frontend && npx tsc -b --noEmit && npx eslint src && npx vite build
```

The roster is already imported (`backend/data/app.db` exists, gitignored).
Backend needs `JWT_SECRET` (already in `backend/.env`) + the Vertex/Qdrant creds.

### Demo logins (pre-seeded passwords — **demo only, in `data/app.db`**)
| Employee ID | Password | Name | Band |
|---|---|---|---|
| `E101` | `demopass123` | Rahul | 9 |
| `E107` | `demopass123` | Lakshay | 3 |

The other 6 are **un-activated** (no password by design) — activate via the UI
(needs the roster email) or seed more. Emails/bands: E102 ashok 7, E103
ravi.ranjan 8, E104 shaksham 4, E105 kunal 10, E106 chirag 6, E108 chirag.grover 7.

**Proof test:** log in as E101 → ask "What's my daily allowance for a 4-day trip
to Mumbai?" → note figures. Sign out → log in as E107 → same question → the UI
re-personalizes (name + Band 3 chip) **and** the numbers differ. Same question,
different login → different chrome + different answer = personalization proven.

---

## Key files (this session)

**New (backend):** `api/security.py`, `api/ratelimit.py`, `api/routes/auth.py`,
`import_employees.py`, `db/` (`base.py`,`models.py`,`session.py`),
`tests/` (`conftest.py`,`test_auth.py`,`test_import.py`,`test_chat.py`),
`requirements-dev.txt`.
**Modified (backend):** `api/main.py`, `api/deps.py`, `api/routes/chat.py`,
`api/schemas.py`, `config/settings.py`, `llm/prompts.py`,
`pipelines/rag_pipeline.py`, `.gitignore`, `requirements*.txt`. Deleted-from-git:
`data/Copy of Team.xlsx` (untracked, still on disk).

**New (frontend):** `hooks/AuthProvider.tsx`, `hooks/useAuth.ts`,
`components/guards.tsx`, `components/auth/AuthField.tsx`, `routes.tsx`.
**Modified (frontend):** `lib/api.ts`, `hooks/useChatStream.ts`,
`pages/AuthPage.tsx`, `pages/ChatPage.tsx` (mobile drawer + top bar + a11y live
region), `components/Sidebar.tsx` (`SidebarContent` split, account menu,
registry-driven Policies list), `components/Welcome.tsx`,
`components/ThinkingIndicator.tsx`, `main.tsx`, `index.css` (auth-swap keyframes).
Added dep **`radix-ui`** (`DropdownMenu` + `Dialog`).
**Deleted (frontend):** `components/ui/button.tsx` + `components/ui/button-variants.ts`
(shadcn button dropped for plain Tailwind), `pages/LoginPage.tsx` /
`ActivatePage.tsx` / `AuthShell.tsx` (consolidated into `AuthPage`).

---

## Design decisions worth knowing
- **Band is server-authoritative.** JWT carries only `sub`; band/name/role are
  looked up per request. `/auth/me` exposes the user their *own* profile (not a
  secret from them) — they just can't spoof it or see others'.
- **Anti-enumeration**: generic 400/401 + equalized bcrypt timing; no endpoint
  reveals which ids/emails exist.
- **Layering**: the pipeline duck-types `.band` (via `UserContext` Protocol) and
  never imports from the `api` layer.
- **Stateless pipeline preserved**: history + band passed in per call.

## Consciously deferred / known limitations (right-sized for an internal tool)
- **Alembic**: deferred. `init_db()` uses `create_all`; introduce Alembic with the
  *first real schema change* (e.g. leave-accrual columns) as migration #1.
- **Rate limiters are in-memory/single-process**: reset on restart, not shared.
  (`/chat` now has a per-user cap; login a per-IP+id cap.) For public/
  multi-process → edge (nginx/Cloudflare) or Redis.
- **JWT has no revocation** (12h expiry; rotate `JWT_SECRET` to invalidate all).
- **localStorage JWT** (XSS tradeoff documented) → httpOnly+SameSite cookie before
  public exposure.
- **Eval harness still travel-only** (`eval.py`, 22 cases) — leave/router/
  cross-scope paths have no gold cases. Add after auth settles.
- **Source PDFs not in repo** (gitignored); Qdrant Cloud is populated but a fresh
  clone can't re-ingest without them.

---

## Suggested next steps
1. **Commit this work** (nothing is committed). Suggested split: (a) auth backend
   + tests, (b) hardening, (c) UI personalization.
2. **Update stale docs**: root `CLAUDE.md` "Current milestone" still says Piece A
   is what remains; `docs/HANDOFF.md`, `docs/ROADMAP.md`,
   `docs/AUTH_PERSONALIZATION_DESIGN.md` still call this future work.
3. Add **leave/router eval gold cases**.
4. Optional polish: role-aware UI (admin tag), per-IP rate cap, `/auth/me` caching.

## Housekeeping
- `frontend/.claude/skills/react-doctor/SKILL 2.md` is an editor-duplicated stray
  (note the " 2" in the name) — safe to delete.
- `frontend/CLAUDE.md` still lists `ui/button` under `src/components/` — stale now
  that the shadcn button is removed; drop that line when touching it.
- Demo passwords for E101/E107 live in `data/app.db` — never ship that DB.
