"""Shared FastAPI dependencies."""
from fastapi import Request

from conversation.store import ConversationStore
from pipelines.rag_pipeline import RAGPipeline


def get_pipeline(request: Request) -> RAGPipeline:
    """Return the single RAGPipeline built once at startup (see api/main.py lifespan)."""
    return request.app.state.pipeline


def get_sessions(request: Request) -> ConversationStore:
    """Return the process-wide per-conversation memory store."""
    return request.app.state.sessions
