# How to Run the RAG System

Follow these steps in order the first time you set up the project.

---

## Step 1 — Create and activate a virtual environment

See `venvcreation.txt` for the full commands.

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## Step 2 — Add your credentials to the .env file

Create or edit the `.env` file in the project root with the following:

```
GOOGLE_APPLICATION_CREDENTIALS=./your-service-account-key.json
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
QDRANT_API_KEY=your-qdrant-api-key
```

- `GOOGLE_APPLICATION_CREDENTIALS` — path to your GCP service account JSON key file.
  Get it from: GCP Console → IAM & Admin → Service Accounts → Keys → Add Key
- `GOOGLE_CLOUD_PROJECT` — your GCP project ID (visible in the GCP Console header)
- `QDRANT_API_KEY` — from Qdrant Cloud dashboard → your cluster → API Keys tab

---

## Step 3 — Add your PDF

Place your PDF file in the project root folder and update `config/settings.py`:

```python
pdf_path: str = "YourDocument.pdf"
```

---

## Step 4 — Ingest the PDF into Qdrant (run once)

This loads the PDF, splits it into chunks, embeds them, and uploads to Qdrant Cloud.

```powershell
python create_db.py
```

You only need to run this again if you change the PDF or want to re-index.

---

## Step 5 — Start the chatbot

```powershell
python main.py
```

You will see:
```
RAG System Ready
Flow: Rewrite -> HYDE -> Hybrid (BM25+Vector MMR) -> Rerank+Filter -> Gemini
Commands: '0' to exit, 'reset' to clear conversation memory

User:
```

Type your question and press Enter. The answer streams token by token.

---

## Commands during the chat session

| Input | Action |
|---|---|
| Any question | Get an answer from the document |
| `reset` | Clear conversation memory (start fresh) |
| `0` | Exit the program |

---

## Tuning parameters

All settings live in `config/settings.py`. Key ones to adjust:

| Setting | Default | Effect |
|---|---|---|
| `chunk_size` | 1000 | Larger = more context per chunk |
| `rerank_score_threshold` | 0.3 | Lower = more chunks pass through |
| `hyde_enabled` | True | Disable to speed up retrieval |
| `history_window` | 4 | Number of past turns kept in memory |
| `vector_k` | 5 | Number of chunks retrieved from vector search |
| `bm25_k` | 5 | Number of chunks retrieved from BM25 search |
