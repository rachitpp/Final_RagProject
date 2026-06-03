"""Per-conversation memory store.

The RAGPipeline is built once and shared by every request, so it must NOT hold
conversation state. Instead the web layer keeps one ConversationMemory per
`conversation_id` here, looks it up on each /chat call, feeds its turns to the
(stateless) pipeline for follow-up rewriting, and appends the new turn after.

This is intentionally an in-memory dict: simple, fine for a single-process demo.
Swap it for Redis / a DB later for multi-process or persistent history — the
interface (get / reset) stays the same.
"""
from conversation.memory import ConversationMemory
from config.settings import settings


class ConversationStore:
    def __init__(self, max_turns: int | None = None) -> None:
        self._max_turns = max_turns or settings.history_window
        self._sessions: dict[str, ConversationMemory] = {}

    def get(self, conversation_id: str) -> ConversationMemory:
        """Return this conversation's memory, creating it on first use."""
        memory = self._sessions.get(conversation_id)
        if memory is None:
            memory = ConversationMemory(max_turns=self._max_turns)
            self._sessions[conversation_id] = memory
        return memory

    def reset(self, conversation_id: str) -> None:
        """Drop a conversation's history (used by 'New chat')."""
        self._sessions.pop(conversation_id, None)
