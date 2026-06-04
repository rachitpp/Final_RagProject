# Project Overview — What It Is & The Techniques Behind It

## In one sentence

This is an **AI assistant that answers questions about a company's travel-
reimbursement policies** by reading the actual policy PDF — not from memory, but
by looking up the relevant text every time and answering strictly from it.

## The problem it solves

Company travel policies are dense: rate tables, city categories, bands, separate
rules for domestic vs overseas trips, and exceptions buried in footnotes. A new
employee asking *"How much can I claim for a 3-day trip to Pune?"* would have to
hunt through pages of tables.

This assistant does that hunting instantly — and, crucially, **grounds every
answer in the real document** and cites the page, so you can trust and verify it.

## What makes it different from "just asking ChatGPT"

A plain chatbot answers from whatever it memorised during training. It will
happily **make up** a travel rate that sounds plausible but is wrong. This project
uses **RAG** so the model can only answer from *your* document — and is told to
say "I couldn't find it" rather than guess.

---

## The big idea: RAG (Retrieval-Augmented Generation)

RAG has three letters' worth of meaning:

- **Retrieval** — first, *find* the parts of the document relevant to the question.
- **Augmented** — *add* those parts to the prompt as context.
- **Generation** — the LLM *writes* an answer using only that context.

> **Analogy:** It's an open-book exam. The model isn't recalling facts from
> memory; it's handed the exact pages it needs and told "answer using these."

This is why the answers are accurate, current, and citable — and why you can swap
in a new PDF without retraining anything.

---

## The technology stack

| Layer | Technology | Role |
|---|---|---|
| **Language model** | Google **Gemini 2.5 Flash** (Vertex AI) | Writes the answers |
| **Embeddings** | Google **text-embedding-004** (Vertex AI) | Turns text into meaning-vectors (768 numbers) |
| **Vector database** | **Qdrant Cloud** | Stores vectors; finds the closest matches |
| **Keyword search** | **BM25** (`rank-bm25`) | Classic exact-term search |
| **Framework** | **LangChain** | Glue between models, retrievers, and the DB |
| **PDF parsing** | **pdfplumber** | Extracts text *and tables* from the PDF |
| **API** | **FastAPI** | Streaming `/chat` endpoint the frontend calls |
| **Web UI** | **React + Vite** (see `../frontend/`) | The chat interface |
| **Tracing** | **LangSmith** | Lets you inspect every step of a query |
| **Language** | **Python 3.13** | — |

Everything AI-related runs **in the cloud** (Vertex AI + Qdrant Cloud), so the
project itself stays lightweight — no GPUs, no PyTorch, no heavy local models.

---

## The techniques used (in plain language)

### 1. Embeddings & semantic search
Text is converted into vectors — long lists of numbers where **similar meaning =
similar numbers**. To find relevant text, we embed the question and ask Qdrant for
the chunks whose vectors are closest. This finds matches by *meaning*, so
"overseas trip" can match a chunk about "foreign travel" even with no shared words.

### 2. Hybrid retrieval (keyword + meaning), scoped to one policy
Semantic search is great for paraphrases but can miss **exact terms** like
"Category A" or "DA". So the project runs **both**:
- **BM25** for precise keyword hits, and
- **vector search** for meaning,

then merges and de-duplicates the results — the precision of keywords with the
flexibility of meaning.

Crucially, **both searches are restricted to one policy.** A small upfront step
classifies each question as Domestic or Foreign, and that decision filters
retrieval (a Qdrant metadata filter for vectors, a separate BM25 index per
policy) so a Domestic question never pulls Foreign chunks, and vice versa. This
**policy isolation is done by the retriever, not the prompt** — which is why the
two policies (which reuse the same A/B/C labels and the same "DA" abbreviation
for different things) can't cross-contaminate an answer.

### 3. Table-aware document parsing
The whole policy lives in **tables** (rate matrices, city categories). Naive PDF
readers turn tables into scrambled text. Here, `pdfplumber` extracts tables
separately and re-renders them as clean **Markdown tables**, even **stitching
tables that span two pages** back together. Good answers depend on good parsing —
this is a quiet but critical technique.

### 4. Guaranteed context ("pinned" reference tables)
The most-needed tables (city/country classification and the rate matrix) ironically
score *badly* in similarity search and get dropped. Rather than fight that, the
pipeline **always injects them**: **both** policies' classification tables (tiny,
and a safety net for the category lookup) plus **only the active policy's rate
matrix** (so a Domestic answer never sees the Foreign currency, and vice versa).
Don't gamble on search finding the data you *know* is always needed — guarantee it.

### 5. Query rewriting (so follow-ups work)
*"What about there?"* means nothing alone. Using recent conversation history, the
system rewrites follow-ups into standalone questions before searching — but only
when it detects a genuine follow-up, leaving clear questions untouched.

### 6. HYDE — Hypothetical Document Embeddings (built, currently off)
A technique where the LLM writes a *fake* answer paragraph in formal policy
language, and we embed *that* (richer than the bare question) to search with. It's
implemented but disabled, because on this small corpus the simpler retrieval
already finds everything. It's there to switch on if the document set grows.

### 7. Prompt engineering: separate "how to reason" from "the data"
The answering prompt is large and detailed — but it contains **zero policy
numbers**. It only encodes *behaviour*: use the trip type it's given (the
retriever already isolated the policy, so the prompt doesn't fight to keep them
apart), resolve a city's category before quoting figures and show the one-line
reason, lead with the direct answer, stay precise, total up multi-day arithmetic,
cite the page. Every actual figure comes from the retrieved context. The litmus
test the author used: *"If the PDF changed tomorrow, would this line be wrong?"*
If yes, it's data and doesn't belong in the prompt.

### 8. Grounded citations
Each chunk is labelled with its source and page before being shown to the model,
and the prompt only allows citations that exist in that context. This prevents the
classic failure where an AI invents an official-looking "Section 4.2, p.12."

### 9. Streaming responses
Answers are sent **token by token** so the user sees text appear live, instead of
waiting for the whole reply — the same feel as ChatGPT.

### 10. Conversation memory
A small buffer keeps the last few turns so the assistant understands context
across questions, without any database or persistence — it simply resets on "New
chat."

### 11. Observability (LangSmith tracing)
Each stage (rewrite, retrieve, answer) is traced, so a developer can open a single
query and see exactly what was retrieved and why — invaluable for debugging *why*
an answer came out the way it did.

---

## How the project is organised

```
Final_RagProject/
├── create_db.py            # Run once: build the vector database from the PDF
├── main.py                 # Command-line chat
│
├── config/settings.py      # All tunable settings in one place
│
├── ingestion/              # PDF → chunks → vectors  (the ingestion pipeline)
│   ├── loader.py           #   table-aware PDF parsing + cleaning
│   ├── splitter.py         #   chunking
│   └── vector_store.py     #   embed + store in Qdrant
│
├── retrieval/              # Finding the right chunks  (the query pipeline)
│   ├── classify.py         #   route to Domestic vs Foreign policy
│   ├── retrievers.py       #   BM25 + vector hybrid search (policy-scoped)
│   ├── pinned.py           #   guaranteed reference tables
│   ├── rewrite.py          #   follow-up query rewriting
│   ├── hyde.py             #   hypothetical-document expansion (optional)
│   └── formatter.py        #   build the context string with citations
│
├── llm/
│   ├── models.py           # Gemini + embedding model setup
│   └── prompts.py          # The reasoning prompts (no policy data inside)
│
├── conversation/           # Short conversation history
│   ├── memory.py           #   sliding-window buffer
│   └── store.py            #   per-conversation store (keyed by id)
├── pipelines/              # Orchestration: ties the steps together
│   ├── ingestion_pipeline.py
│   └── rag_pipeline.py     # The main RAGPipeline class
│
└── api/                    # FastAPI service (streaming /chat, /reset, /library)
```

A clean separation: **ingestion** prepares the data, **retrieval** finds it,
**llm** reasons over it, **pipelines** orchestrate, and **api** serves it to the
React frontend (`../frontend/`).

---

## The end-to-end story, briefly

1. **Once:** `create_db.py` reads the policy PDFs, cleans them, splits into
   chunks, embeds them with Gemini's embedder, and stores them in Qdrant (tagged
   by policy, with a filter index).
2. **Per question:** the app rewrites the question if needed, **routes it to the
   right policy**, searches Qdrant (meaning) and BM25 (keywords) **within that
   policy**, always adds the key reference tables, formats everything with page
   citations, and asks Gemini to answer **only** from that context — streaming
   the reply back with citations.

The result: fast, trustworthy, **document-grounded** answers about a real travel
policy — with no model hallucination and full traceability.

---

**Related docs**
- `SETUP.md` — get it installed and running
- `PIPELINE.md` — the same flow, step by step, with file references
