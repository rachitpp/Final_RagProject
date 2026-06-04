# Auth + Personalization + Leave Policy — Design Decisions

> Decisions record from the design discussion on **2026-06-04**. This refines
> the inferred plan in [`ROADMAP.md`](ROADMAP.md) into concrete, agreed choices.
> Nothing here is built yet — it is the spec to build against.

## The milestone in one line

Make the assistant **know who is asking** (login → JWT → server-side band lookup)
and **auto-scope every answer to that person's band**, add the **leave policy**
PDF to the corpus, and route queries across the growing multi-domain corpus —
so the LLM stops answering "for every band" and stops saying "you didn't mention
your band."

This is really **two independent bodies of work** that share one foundation:

- **Piece A — Identity & personalization:** login, Excel roster, inject band/grade.
- **Piece B — Registry-driven multi-domain RAG:** the leave PDF + the router.

They can be built in parallel.

---

## Core architecture decisions

### 1. Two stores, two jobs (polyglot persistence)

| Store | Holds | Queried by |
|---|---|---|
| **Vector DB** (Qdrant today) | embedded PDF chunks (travel + leave) — *knowledge* | meaning (semantic similarity) |
| **Relational DB** (SQLite via SQLAlchemy, already pinned) | employee roster, credentials, (later) conversations — *identity* | exact key (`WHERE employee_id = …`) |

**The PDFs are the knowledge; the Excel/roster is the identity.** They meet only
in the prompt: the band (from SQL) wraps the chunks (from the vector DB). There is
**no cross-DB join** — the only link is `employee_id`, stitched in app code.

### 2. NEVER embed the Excel / employee data

The roster goes into a **relational table, looked up by key** — never embedded.
Embedding it would be wrong on every axis:
- vector search is *approximate* → could return the **wrong employee's** band (a
  correctness bug + a PII leak across users);
- band labels like `9/10` don't embed to anything meaningful;
- the roster mutates (people change bands) — a table upserts trivially.

The band is **prompt context + calculator input**, never something you search for.

### 3. Engine choice: Qdrant now / pgvector is a valid consolidation

At ~15–thousands of chunks, performance is a non-issue either way. The decision is
**ops simplicity vs. not rewriting working code**:

- **Option A — Qdrant + SQLite:** least new work (don't touch retrieval). SQLite is
  just a file. **← default for shipping this milestone.**
- **Option B — Qdrant + Postgres:** ❌ avoid — two real servers *and* no
  consolidation (worst of both).
- **Option C — pgvector for both:** one engine; requires rewriting `vector_store.py`
  + the vector leg of `retrievers.py`. Good end-state if you want to drop the Qdrant
  Cloud dependency. Some Qdrant-specific code (strict-mode payload index, scroll)
  *disappears* with it.

**Move to a dedicated vector DB only when a trigger fires:** >~1M vectors, filtered
p95 latency over budget, need quantization for RAM/cost, vector load degrading the
transactional DB, or going multi-tenant SaaS. An internal HR tool likely never hits
these — **pgvector stays correct for the realistic growth path.**

### 4. Access control vs. personalization — we are doing personalization

Two different "per-user" concerns in RAG:
- **Access control** = *which chunks you may retrieve* (per-chunk ACL metadata + a
  mandatory filter).
- **Personalization** = *tailoring the answer* when everyone sees the same docs.

**This project is personalization, not access control.** Every employee can read
the entire travel/leave policy; the band only changes *which row of the rate table
the answer computes*. So we **do NOT need** per-chunk ACLs, collection-per-tenant,
or permission-sync machinery. (We'd only need them if a confidential, band-gated
annex existed.)

---

## Piece B — Registry-driven multi-domain RAG (leave PDF + router)

### 5. The registry is the backbone

`loader.py::_policy_for()` currently sniffs the filename → `domestic`/`foreign`.
Dropping in `leave_policy.pdf` would be **silently tagged `domestic`** and break the
filter. So "embed the leave PDF" is secretly a **data-model change** — and doing it
once gives the router for free.

Replace filename-sniffing with a small **manifest** (one row per PDF: file → domain,
optional sub_policy). Adding a PDF becomes: drop file, add a row, re-ingest.
**Put the manifest in `config/` (a dict / `config/documents.py`), not a stray
`documents.yaml`** — honors the "all tunables in settings" rule and avoids the
documented relative-path footgun ("run from inside `backend/`").

### 6. Metadata: ADD `domain`, KEEP `policy` (don't rename to `sub_policy`)

Lower churn than the rename: keep `policy` (`domestic`/`foreign`, travel's sub-axis,
already indexed) and **add `domain`** (`travel`/`leave`).

**Concrete bug to avoid:** `retrievers.py::build_bm25_by_policy` does
`if not policy: continue` — so any chunk without a `policy` (i.e. leave) is
**silently dropped from BM25**. Fix: make the BM25 group / vector-filter key the
**finest always-present isolation unit** — the *retrieval scope* =
`domestic | foreign | leave`. The router produces the list of scopes to query; loop
`hybrid_retrieve` once per scope and union+dedupe.

### 7. Router: one structured classify call, not two LLM hops

Don't stack a new domain-router LLM call on top of `classify_trip_type` (that's 3–4
sequential LLM hops before streaming). **Extend the existing classify call's output**
to emit both in one shot:
```json
{ "scopes": ["travel"], "trip_type": "domestic" }   // trip_type consulted only when travel ∈ scopes
```
- Handle the **empty scope set** (greeting / off-topic → clarify, don't default to
  domestic-and-retrieve-noise).
- Industry upgrade path (don't build yet): **semantic-router** (embedding centroids,
  no LLM call) when latency/cost bites or domains grow past ~10.
- This is the same idea as LangChain's **query construction / self-query**.

### 8. Pinning, calculator, and the prompt are travel-coupled → gate them

The pipeline always calls `classify_trip_type` + `_merge_pinned` + offers
`compute_entitlement`. For a **leave-only** question these would inject the travel
rate matrix and travel machinery into a leave answer. **Gate classify/pin/calculator
on `"travel" ∈ scopes`.**

On the prompt: at **two domains, keep ONE `ANSWER_PROMPT`** with a leave section that
only activates when leave chunks are present — simpler than maintaining per-domain
prompts you'd have to merge on cross-domain questions.

> Note: `HYDE_PROMPT` is travel-vocabulary-coupled (and off). If re-enabled for
> leave, it'd need a domain-aware variant.

---

## Piece A — Auth & personalization

### 9. Pre-provision from Excel, don't open-register

Only `employee_id`s present in HR's sheet can ever get an account. "Signup" is really
**first-time activation**: the employee proves identity and sets a password.
**`employee_id` is the bridge** — the one field on both sides (user types it; Excel
attaches everything else to it).

### 10. What the user provides vs. what's server-authoritative

- **User provides:** `employee_id` + **password** (first login also: an email-match
  or one-time code to verify, then set the password). **That's all.**
- **User NEVER provides:** band, grade, department, base_city, role. If the user
  could type their band, personalization is spoofable.
- **Server-authoritative (from Excel):** band, grade, and all entitlement attributes.

### 11. JWT carries only `sub` (employee_id)

Not the band. Band/grade are looked up **server-side on every `/chat`** from the DB —
so a band change takes effect immediately and nothing client-held is tamperable.
`get_current_user` (a FastAPI dependency alongside the existing `get_pipeline` /
`get_sessions` in `deps.py`) decodes the token and does the lookup.

### 12. Libraries

- **PyJWT** — already pinned (use this, *not* python-jose).
- **SQLAlchemy** — already pinned (ORM for the users table).
- **`openpyxl` + `pandas`** — already pinned (read the `.xlsx`).
- **bcrypt / passlib[bcrypt]** — **NOT pinned — this is the one real gap to add** for
  password hashing. (`cryptography` is present but is not a password hasher.)
- `pydantic-settings` (pinned) — put the JWT secret here as an env-backed setting.

### 13. Security gap in the current design: `conversation_id`

It's client-generated and unauthenticated (`schemas.py`). After auth, **scope every
conversation to the authenticated `sub`** server-side, or user A can pass user B's
`conversation_id` and read their history.

---

## Data model

### `users` table (columns mirror the real `.xlsx` — finalize against it)

```
employee_id    TEXT PK      -- login identity + join key (the bridge)
email          TEXT UNIQUE  -- from Excel (authoritative); first-login verification
name           TEXT
band           TEXT         -- e.g. "9/10" — drives travel; server-authoritative
grade          TEXT         -- ONLY if the sheet truly separates it from band (see open Qs)
department     TEXT         -- optional
base_city      TEXT         -- optional
role           TEXT         -- 'employee' | 'hr_admin' (often defaulted in code)
password_hash  TEXT NULL    -- null until activation; bcrypt; the only secret stored
activated_at   TIMESTAMP NULL
created_at / updated_at
```

### What goes IN SQL

- **Roster/identity** — written at **Excel import**; **read on every query** (the band
  lookup). Imported once, then read — never re-saved per query.
- **Credentials** — `password_hash` written at **signup**; read at every login.
- **Conversation history** — currently **in-memory** (`ConversationStore`); moving it
  to SQL later is a **separate table with an FK to `users`** (same DB, not a new
  system). Optional for the first cut.

### What the Excel should contain

`employee_id` (unique), `band`, `email`, `name` required; `grade`/`department`/
`base_city` optional. **NOT** passwords (HR never sees them) and **NOT** policy data
(that's the PDFs). **Band values must match the policy's labels** (e.g. `9/10`) — a
mismatch (`"Band 9"` vs `"9/10"`) breaks the injected lookup. Validate at import.

### `import_employees.py` — don't drop-and-reload

`create_db.py` / `vector_store.py` *delete and rebuild* the Qdrant collection. Do NOT
mirror that for the users table — a drop-reload would **wipe everyone's
`password_hash`** on every HR refresh. **Upsert by `employee_id`** (update roster
fields, leave credentials untouched), or split credentials into their own table the
import never touches. Excel is the source of truth **at import time**, not read live
per request.

---

## End-to-end workflow (target)

**Login (once per session):**
1. User submits `employee_id` + password → `POST /login`.
2. Backend looks up the row, verifies password vs `password_hash` (bcrypt), issues a
   JWT `{ sub: employee_id }` (PyJWT).
3. Frontend stores the token, sends `Authorization: Bearer <JWT>` on every call.

**Each query:**
4. `POST /chat` with question + conversation_id + JWT.
5. `get_current_user` decodes the JWT → `employee_id` (401 if invalid/expired).
6. `SELECT band, grade FROM users WHERE employee_id = sub` → `user_profile` (identity).
7. History from `ConversationStore` (scoped to this user).
8. `pipeline.stream_answer(question, history, user_profile)`:
   - rewrite → route (scopes + trip_type) → hybrid_retrieve per scope → union+dedup
   - pin tables (travel only) → format context
   - `ANSWER_PROMPT` + `{employee_context: band}` → Gemini stream ⇄
     `compute_entitlement(single band)`
9. Tokens stream to the UI; on completion the `(Q, A)` turn is saved.

**Result:** the answer is scoped to the user's band automatically — no "you didn't
mention your band" hedge.

---

## Build delta (what's new vs. what exists)

**Already exists** (most of the query path): rewrite, classify (travel), hybrid
retrieve, pinning, format, the answer prompt, the `compute_entitlement` tool loop,
streaming, the stateless pipeline + per-conversation store, `@traceable` + `eval.py`.

**To build:**
- *Piece A:* `/login` route, users table + `import_employees.py`, bcrypt hashing,
  JWT issue/verify, `get_current_user` dep, `user_profile` arg into `stream_answer`,
  the `{employee_context}` prompt block (flip "all bands" → the user's band, kept as
  fallback), single-band calculator call, conversation scoping, frontend login
  page/auth state + attach the JWT.
- *Piece B:* the document manifest (config), `domain` metadata + the retrieval-scope
  key (fix the BM25 drop bug), ingest the leave PDF, the structured multi-scope
  router, gate pin/calculator/prompt to travel, the conditional leave prompt section.

---

## Open questions / unverified assumptions (resolve before coding)

1. **band vs. grade** — the "band drives travel, grade drives leave" split is an
   *assumption*, not a verified fact. The existing tables key on **band** (`9/10`).
   Don't hardcode a `grade→leave` mapping until you've seen the real sheet + leave PDF.
   Don't add a `grade` column if the sheet only has `band`.
2. **The real `.xlsx` schema** — finalize `users` columns against the actual file.
3. **The leave PDF structure** — eyeball its chunks after ingest (it's the same DCM
   portal export `loader.py` already strips, so ingestion should mostly just work).

## Recommended build order

0. **Get the real leave PDF + `.xlsx` in hand and read them** (they decide the schema,
   the `domain` values, and the band/grade question).
1. Registry (manifest + `domain` metadata + the retrieval-scope key / BM25 fix).
2. Ingest leave through the registry; eyeball chunks.
3. Structured multi-scope router; gate pin/calculator/prompt to travel.
4. Auth + Excel import (users table, bcrypt, JWT, `get_current_user`).
5. Context injection (`user_profile` arg + conditional prompt + single-band calculator).

Steps 1–3 and 4–5 are independent.
