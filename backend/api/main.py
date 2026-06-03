"""FastAPI entry point.

Run from the `backend/` directory so relative paths (.env, ./Project_123.json)
resolve:

    cd backend
    ./venv/bin/uvicorn api.main:app --reload --port 8000
"""
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()  # load .env (Vertex creds, Qdrant key) before building the pipeline

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pipelines.rag_pipeline import RAGPipeline
from conversation.store import ConversationStore
from api.routes import chat, health, meta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
)

# Frontend dev origin (Vite). Add the deployed origin here later.
ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Build the heavy pipeline ONCE (loads vector store, BM25, pinned tables).
    app.state.pipeline = RAGPipeline()
    # Per-conversation memory store (keyed by conversation_id).
    app.state.sessions = ConversationStore()
    logging.getLogger(__name__).info("Pipeline ready; API is up.")
    yield
    # nothing to tear down


app = FastAPI(title="RAG Assistant API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(meta.router)
