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
| **Framework** | **LangChain** | Glue between models, retrievers, and the DB |
| **PDF parsing** | **pdfplumber** | Extracts text *and tables* from the PDF |
| **Web UI** | **Streamlit** | The chat interface |
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

### 2. Semantic search, scoped to one policy
To find relevant text, the project embeds the question and asks Qdrant for the
chunks whose vectors are closest in **meaning** — so "overseas trip" matches a
chunk about "foreign travel" even with no shared words.

Crucially, **the search is restricted to one policy.** A small upfront step
classifies each question as Domestic or Foreign, and that decision filters
retrieval (a Qdrant metadata filter on `policy`) so a Domestic question never
pulls Foreign chunks, and vice versa. This **policy isolation is done by the
retriever, not the prompt** — which is why the two policies (which reuse the
same A/B/C labels and the same "DA" abbreviation for different things) can't
cross-contaminate an answer.

> **Why not hybrid (keyword) search?** An earlier version also ran BM25 keyword
> search alongside the vector search and merged the results. On this tiny corpus
> (~15 chunks), an A/B run of the eval harness showed it made no difference —
> vector search with `k=10` already recalls almost the entire policy sub-corpus,
> and the must-have tables are guaranteed by pinning (technique 4) regardless. So
> it was removed in favour of the simpler vector-only path. Same story for HYDE
> and a cross-encoder reranker: measured, found inert at this size, removed.

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

### 6. Prompt engineering: separate "how to reason" from "the data"
The answering prompt is large and detailed — but it contains **zero policy
numbers**. It only encodes *behaviour*: use the trip type it's given (the
retriever already isolated the policy, so the prompt doesn't fight to keep them
apart), resolve a city's category before quoting figures and show the one-line
reason, lead with the direct answer, stay precise, total up multi-day arithmetic,
cite the page. Every actual figure comes from the retrieved context. The litmus
test the author used: *"If the PDF changed tomorrow, would this line be wrong?"*
If yes, it's data and doesn't belong in the prompt.

### 7. Grounded citations
Each chunk is labelled with its source and page before being shown to the model,
and the prompt only allows citations that exist in that context. This prevents the
classic failure where an AI invents an official-looking "Section 4.2, p.12."

### 8. Streaming responses
Answers are sent **token by token** so the user sees text appear live, instead of
waiting for the whole reply — the same feel as ChatGPT.

### 9. Conversation memory
A small buffer keeps the last few turns so the assistant understands context
across questions, without any database or persistence — it simply resets on "New
chat."

### 10. Observability (LangSmith tracing)
Each stage (rewrite, retrieve, answer) is traced, so a developer can open a single
query and see exactly what was retrieved and why — invaluable for debugging *why*
an answer came out the way it did.

---

## How the project is organised

```
Final_RagProject/
├── create_db.py            # Run once: build the vector database from the PDF
├── main.py                 # Command-line chat
├── app.py                  # Streamlit web chat
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
│   ├── retrievers.py       #   vector (semantic) search (policy-scoped)
│   ├── pinned.py           #   guaranteed reference tables
│   ├── rewrite.py          #   follow-up query rewriting
│   └── formatter.py        #   build the context string with citations
│
├── llm/
│   ├── models.py           # Gemini + embedding model setup
│   └── prompts.py          # The reasoning prompts (no policy data inside)
│
├── conversation/memory.py  # Short conversation history
├── pipelines/              # Orchestration: ties the steps together
│   ├── ingestion_pipeline.py
│   └── rag_pipeline.py     # The main RAGPipeline class
│
├── ui/                     # Streamlit UI logic (rendering, sidebar, behaviours)
└── styles/                 # The UI's CSS
```

A clean separation: **ingestion** prepares the data, **retrieval** finds it,
**llm** reasons over it, **pipelines** orchestrate, and **ui** presents it.

---

## The end-to-end story, briefly

1. **Once:** `create_db.py` reads the policy PDFs, cleans them, splits into
   chunks, embeds them with Gemini's embedder, and stores them in Qdrant (tagged
   by policy, with a filter index).
2. **Per question:** the app rewrites the question if needed, **routes it to the
   right policy**, searches Qdrant (by meaning) **within that policy**, always
   adds the key reference tables, formats everything with page citations, and
   asks Gemini to answer **only** from that context — streaming the reply back
   with citations.

The result: fast, trustworthy, **document-grounded** answers about a real travel
policy — with no model hallucination and full traceability.

---

**Related docs**
- `SETUP.md` — get it installed and running
- `PIPELINE.md` — the same flow, step by step, with file references
