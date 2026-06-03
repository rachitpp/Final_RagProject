"""Chat endpoint — streams the RAG answer token by token as plain text.

Conversation memory is per `conversation_id`: we read this conversation's prior
turns, feed them to the (stateless) pipeline for follow-up rewriting, and append
the completed turn afterwards. Starlette runs the sync generator in a threadpool,
so the blocking LLM stream doesn't stall the event loop.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from api.deps import get_pipeline, get_sessions
from api.schemas import ChatRequest, ResetRequest
from conversation.store import ConversationStore
from pipelines.rag_pipeline import RAGPipeline

router = APIRouter()


@router.post("/chat")
def chat(
    body: ChatRequest,
    pipeline: RAGPipeline = Depends(get_pipeline),
    sessions: ConversationStore = Depends(get_sessions),
) -> StreamingResponse:
    memory = sessions.get(body.conversation_id)
    history = memory.turns()

    def generate():
        parts: list[str] = []
        for piece in pipeline.stream_answer(body.question, history):
            parts.append(piece)
            yield piece
        # Save only after a complete stream (skipped if the client disconnects).
        memory.add(body.question, "".join(parts))

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


@router.post("/reset")
def reset(
    body: ResetRequest,
    sessions: ConversationStore = Depends(get_sessions),
) -> dict:
    """Clear a conversation's history (the 'New chat' action)."""
    sessions.reset(body.conversation_id)
    return {"status": "reset"}
