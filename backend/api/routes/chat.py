"""Chat endpoint — streams the RAG answer token by token as plain text.

Conversation memory is per `conversation_id`: we read this conversation's prior
turns, feed them to the (stateless) pipeline for follow-up rewriting, and append
the completed turn afterwards. Starlette runs the sync generator in a threadpool,
so the blocking LLM stream doesn't stall the event loop.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from api.deps import get_current_user, get_pipeline, get_sessions
from api.schemas import ChatRequest, ResetRequest, UserProfile
from conversation.store import ConversationStore
from pipelines.rag_pipeline import RAGPipeline

router = APIRouter()


def _session_key(user: UserProfile, conversation_id: str) -> str:
    """Namespace the client-supplied conversation_id by employee_id so a user
    can never read or reset another user's memory by guessing/replaying an id."""
    return f"{user.employee_id}:{conversation_id}"


@router.post("/chat")
def chat(
    body: ChatRequest,
    pipeline: RAGPipeline = Depends(get_pipeline),
    sessions: ConversationStore = Depends(get_sessions),
    user: UserProfile = Depends(get_current_user),
) -> StreamingResponse:
    memory = sessions.get(_session_key(user, body.conversation_id))
    history = memory.turns()

    def generate():
        parts: list[str] = []
        for piece in pipeline.stream_answer(body.question, history, user_profile=user):
            parts.append(piece)
            yield piece
        # Save only after a complete stream (skipped if the client disconnects).
        memory.add(body.question, "".join(parts))

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


@router.post("/reset")
def reset(
    body: ResetRequest,
    sessions: ConversationStore = Depends(get_sessions),
    user: UserProfile = Depends(get_current_user),
) -> dict:
    """Clear a conversation's history (the 'New chat' action)."""
    sessions.reset(_session_key(user, body.conversation_id))
    return {"status": "reset"}
