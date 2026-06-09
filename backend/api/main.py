"""FastAPI entry point.

Run from the `backend/` directory so relative paths (.env, ./Project-123.json)
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

from config.settings import settings
from pipelines.rag_pipeline import RAGPipeline
from conversation.store import ConversationStore
from db.session import init_db
from api.routes import auth, chat, health, meta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast if the JWT secret is missing or weak (e.g. .env not loaded), rather
    # than booting and 500-ing on the first login. settings reads it from the
    # JWT_SECRET env var, which load_dotenv() above has already populated. HS256
    # wants >= 32 bytes (256 bits) of key; `secrets.token_urlsafe(48)` clears that.
    if len(settings.jwt_secret) < 32:
        raise RuntimeError(
            "JWT_SECRET is missing or too short (need >= 32 chars). Set a strong "
            "value in backend/.env, e.g. `python -c \"import secrets; "
            "print(secrets.token_urlsafe(48))\"`."
        )
    # Ensure the users table exists (no-op if already created by the importer).
    init_db()
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
    # Configurable via CORS_ALLOW_ORIGINS (see config/settings.py); defaults to
    # the Vite dev origin. Set the deployed frontend origin(s) in production.
    allow_origins=list(settings.cors_allow_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(meta.router)
