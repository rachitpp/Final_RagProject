# Pipeline Breakdown — How a Question Becomes an Answer

This project has **two** pipelines:

1. **Ingestion** — runs once (via `create_db.py`). Turns your PDF into searchable
   vectors stored in Qdrant.
2. **Query** — runs on every question (via `main.py` or the FastAPI `/chat`
   endpoint in `api/`). Finds the right pieces of the PDF and asks Gemini to
   answer from them.

Below, each stage names the exact file it lives in, so you can follow along in
the code.

---

## Part 1 — The Ingestion Pipeline (run once)

**Goal:** take a PDF full of policy text and tables, and store it in a form that
can be searched by *meaning* and by *keyword*.

```
PDF  ─►  Load & clean  ─►  Split into chunks  ─►  Embed  ─►  Store in Qdrant
        (pdfplumber)       (text splitter)       (Gemini)     (vector DB)
```

Entry point: `create_db.py` → `pipelines/ingestion_pipeline.py:run_ingestion()`

### Step 1 — Load & clean the PDF
**File:** `ingestion/loader.py`

The policy PDF is a web page exported to PDF, so every page repeats junk: a
"Welcome… Logout" header, a nav strip, footer URLs, "Page X of Y". The loader:

- **Strips this "page chrome"** so it never pollutes the search.
- **Extracts tables separately from prose.** Tables (rate matrices, city lists)
  are pulled out and re-rendered as clean **Markdown tables**, while the
  surrounding narrative text is kept apart so numbers aren't duplicated in a
  mangled form.
- **Stitches tables that break across pages** back into one self-describing
  table (e.g. the band-rate matrix that spans a page boundary).
- **Tags every chunk** with its origin and policy:
  `{"source": "domestic travel.pdf", "page": 2, "policy": "domestic"}`. The
  `page` is **1-based** (the real PDF page, so citations read `p.2`, not `p.0`),
  and `policy` (`domestic`/`foreign`, derived from the filename) is what lets
  retrieval later keep the two policies apart.

Output: a list of `Document` objects, one per page, each holding cleaned text +
markdown tables + source/page/policy metadata.

### Step 2 — Split into chunks
**File:** `ingestion/splitter.py`

LLMs and embeddings work best on **small, focused pieces**, not whole pages. A
`RecursiveCharacterTextSplitter` cuts each document into overlapping chunks:

- `chunk_size = 1500` characters — big enough to keep a whole rate table in one
  piece (so it isn't split mid-table).
- `chunk_overlap = 80` — a little repetition between neighbours so a sentence cut
  at a boundary still appears whole in one chunk.
- It prefers to split on natural boundaries (`\n\n`, then `\n`, then `. `).

### Step 3 — Embed the chunks
**File:** `ingestion/vector_store.py` + `llm/models.py`

Each chunk is turned into an **embedding** — a list of 768 numbers that captures
its *meaning*. Done by Google's `text-embedding-004` model on Vertex AI.
Chunks with similar meaning end up with similar number-lists, which is what makes
"search by meaning" possible. Embedding happens in batches of 200.

### Step 4 — Store in Qdrant
**File:** `ingestion/vector_store.py`

The embeddings (plus the original text and metadata) are uploaded to a **Qdrant
Cloud** collection called `rag_documents`, configured for **cosine similarity**
(the measure of "how close in meaning").

> Because `create_db.py` is a *full rebuild*, it **drops the existing collection
> first** and recreates it. This prevents stale, leftover chunks from polluting
> future searches.

It also creates **keyword payload indexes on `metadata.policy` and
`metadata.scope`** (the scope — `domestic | foreign | leave` — is what retrieval
filters on). Qdrant Cloud often runs in *strict mode*, which rejects filtering
on an unindexed field — so these indexes are what make the scoped retrieval
filter (Query Step 4) actually work, not just a speed-up.

When this finishes, your PDFs are fully searchable. You won't run ingestion again
unless the PDFs change — and re-running it is also how new `policy`/`page`
metadata or the index get applied.

---

## Part 2 — The Query Pipeline (every question)

**Goal:** for each user question, gather the *right* pieces of the policy and let
Gemini write a grounded, cited answer.

```
Question
   │
   ▼
1. Rewrite       (resolve "what about there?" into a standalone question)
   │
   ▼
2. Route         (which scope(s) the question touches: Domestic / Foreign / Leave
   │              — multi-label; the single routing decision)
   ▼
3. HYDE          (optional, currently OFF — richer query for vector search)
   │
   ▼
4. Hybrid retrieve   BM25 (keywords) + Vector (meaning), BOTH scoped to the
   │                 routed scope(s)  →  union & dedupe
   ▼
5. Pin tables    (inject the ACTIVE travel policy's classification + rate tables;
   │              leave-only questions pin nothing)
   │
   ▼
6. Format        (stitch chunks into one context string with [source, page] tags)
   │
   ▼
7. Gemini        (answer ONLY from that context, with the trip type supplied; streamed)
   │
   ▼
8. Remember      (save the turn so follow-ups make sense)
```

Everything is orchestrated by the `RAGPipeline` class in
`pipelines/rag_pipeline.py`. It's built **once** at startup (loading the vector
store, BM25 index, LLM, and memory) and reused for every question.

### Step 1 — Rewrite the question
**File:** `retrieval/rewrite.py`

A follow-up like *"what about there?"* is meaningless on its own. Using the last
few conversation turns, the rewriter expands it into a standalone question, e.g.
*"What is the lodging allowance in Pune?"*

It's deliberately conservative:
- If there's **no history**, or the question is **already standalone**, it's left
  unchanged (rewriting clear questions was corrupting them).
- It only rewrites genuine follow-ups — detected by short length or words like
  *it, that, there, same, what about*.

### Step 2 — Route to scope(s)
**File:** `retrieval/classify.py`

The rewritten question is routed to the policy **scope(s)** it touches —
Domestic (within India), Foreign (overseas), and/or Leave — with a single small
LLM call (multi-label: a combined "travel + leave" question unions both). This
is the **one** routing decision in the whole system: it drives the retrieval
filter, which rate table gets pinned, which calculator tools are offered, and
the answer's grounding line, so they can never disagree. The **"assume Domestic
when ambiguous" tie-break lives here**, not in the answer prompt — it applies
when a *trip* is implied but the destination is unclear. If the router LLM
itself is unreachable (after one retry), the pipeline answers with an honest
"please try again" instead of guessing a scope.

> Why isolate policy at retrieval instead of in the prompt? Because the two
> policies reuse the same A/B/C labels and the same abbreviations (e.g. "DA")
> for entirely different things. Keeping only one policy's body + rate table in
> context removes the chance of cross-contamination — the retriever does the
> separating, so the prompt doesn't have to.

### Step 3 — HYDE (optional, currently OFF)
**File:** `retrieval/hyde.py` · toggle: `settings.hyde_enabled` (default `False`)

HYDE = **Hy**pothetical **D**ocument **E**mbeddings. The idea: instead of
embedding the bare question, ask the LLM to *write a fake paragraph that would
answer it* in formal policy language, then embed **that**. A richer, on-vocabulary
query lands closer to the real policy text.

It's **off** here because, on this small corpus, BM25 + vector already find
almost everything, so HYDE added an LLM call for near-zero gain. The code stays
ready — flip the setting on if the corpus grows.

### Step 4 — Hybrid retrieval (scope-isolated)
**File:** `retrieval/retrievers.py`

For **each scope routed in Step 2**, two complementary searches run, then merge:

- **BM25 (keyword search)** — great for exact terms ("Category A", "DA"). Uses a
  custom tokenizer (lowercase, strip punctuation) so `Pune.` matches `pune`. A
  **separate BM25 index per scope** is built at startup; the matching one is used.
- **Vector search (meaning search)** — great for paraphrases and synonyms,
  filtered on `metadata.scope` so only the routed scope's chunks come back.
  (This filter needs a Qdrant payload index — created at ingestion; see Part 1.)
  The query is embedded **once** and the vector is reused across scopes.

Each leg returns up to `k = 10` chunks. Per-scope results are **unioned and
de-duplicated** (by exact text). Keyword precision + semantic recall = high
coverage, all within the routed scope(s).

Scope isolation **fails closed**: if the filtered vector search errors, that
query degrades to the (still scope-isolated) BM25 leg — there is deliberately
no unfiltered fallback, because leaking the other policy's chunks (same A/B/C
labels, different currencies) is worse than finding nothing. An untagged corpus
is rejected at startup with instructions to re-run `create_db.py`.

### Step 5 — Pin the reference tables
**File:** `retrieval/pinned.py`

Almost every answer needs two kinds of lookup table: the **classification**
(which category a place is) and the **rate matrix** (the amounts). But these dense
tables score *poorly* in similarity search and often get pushed out of the top
results — exactly when they're needed most.

So instead of hoping search finds them, the pipeline **guarantees** them. At
startup it resolves each table by a stable text signature; per query it injects
**only the active travel policy's** classification table and rate matrix (so a
Domestic answer never sees the Foreign `$` rates, and vice versa). Leave-only
questions pin nothing — leave has no rate tables.

Retrieval owns *"is the right reference data present?"*; the prompt just looks it
up instead of guessing.

### Step 6 — Format the context
**File:** `retrieval/formatter.py`

The chosen chunks are joined into one text block, each tagged with its origin:

```
[Chunk 1 | domestic travel.pdf, p.2]
<chunk text…>

---

[Chunk 2 | domestic travel.pdf, p.4]
<chunk text…>
```

Those `source, page` tags are what let Gemini cite a real section and page. The
`page` is **1-based** (the actual PDF page number), set at ingestion — so a
citation reads `p.2`, never `p.0`.

### Step 7 — Answer with Gemini
**File:** `llm/prompts.py` (the `ANSWER_PROMPT`) + `llm/models.py`

The context + question + the **already-decided trip type** go to
**`gemini-2.5-flash`** on Vertex AI, with a structured instruction prompt that
encodes *how to reason and present*:

- The trip type is **given** (from Step 2) — the prompt uses it, it does not
  re-derive it.
- **Resolve the category** of any named city/country *before* quoting figures,
  and always show the one-line basis ("Pune is Category A (explicitly listed)").
- Read each table by its own key (a rate may depend on category; a travel class
  on band — never assume one decides the other).
- If the band or arrangement is missing, **answer for all bands** as a table
  rather than refusing.
- Carry multi-day / multi-leg **arithmetic all the way to a total**.
- **Lead with the direct answer**, stay precise (no padding), and **cite**
  section + page only when present in the context.

A key design rule: **the prompt never contains policy data** (no rates,
thresholds, or category lists). All facts come from the retrieved context, which
is the single source of truth. If the PDF changes tomorrow, the prompt is still
correct.

The answer is **streamed token by token** so the user sees it appear live.

### Step 8 — Remember the turn
**File:** `conversation/memory.py`

The question and answer are stored in a small in-memory buffer that keeps the
last `history_window = 4` turns. That's what Step 1 (rewrite) reads to make
follow-up questions work. It resets when you type `reset` (CLI) or click
**New chat** (web).

---

## Where each setting lives

All tunable numbers are in **`config/settings.py`**:

| Setting | Default | Effect |
|---|---|---|
| `chunk_size` | 1500 | Characters per chunk (kept large to fit whole tables) |
| `chunk_overlap` | 80 | Shared text between neighbouring chunks |
| `vector_k` | 10 | Chunks pulled from vector (meaning) search |
| `bm25_k` | 10 | Chunks pulled from BM25 (keyword) search |
| `hyde_enabled` | False | Turn the HYDE query-expansion step on/off |
| `history_window` | 4 | Conversation turns kept for follow-ups |
| `embedding_model` | text-embedding-004 | Vertex embedding model (768 dims) |
| `llm_model` | gemini-2.5-flash | The answering model |

> **Note:** there is intentionally **no reranker** in the current pipeline. On
> this small, table-heavy corpus a cross-encoder reranker scored the key tables
> near zero and dropped them, so it was removed in favour of the simpler
> BM25 + vector + pinned-tables approach above.

---

**Related docs**
- `SETUP.md` — install and run the project
- `OVERVIEW.md` — the concepts and techniques behind this design
