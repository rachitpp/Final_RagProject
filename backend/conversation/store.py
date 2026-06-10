"""Per-conversation memory store.

The RAGPipeline is built once and shared by every request, so it must NOT hold
conversation state. Instead the web layer keeps one ConversationMemory per
`conversation_id` here, looks it up on each /chat call, feeds its turns to the
(stateless) pipeline for follow-up rewriting, and appends the new turn after.

This is intentionally an in-memory store: simple, fine for a single-process
deployment. It is bounded two ways so it can never grow without limit:

- **LRU cap** — at most `max_sessions` conversations are kept; touching a
  conversation moves it to the most-recently-used end, and overflow evicts
  from the least-recently-used end.
- **TTL** — a conversation idle longer than `ttl_seconds` is dropped on the
  next store access. Because entries are kept in last-used order, expired
  ones are always a contiguous run at the LRU end — the sweep stops at the
  first live entry, so it's O(expired), not O(all).

Eviction only forgets *history* (follow-up context), never data: the next
message on an evicted conversation just starts with empty memory.

Swap this for Redis later for multi-process or persistent history — the
interface (get / reset) stays the same.
"""
import threading
import time
from collections import OrderedDict

from conversation.memory import ConversationMemory
from config.settings import settings


class ConversationStore:
    def __init__(
        self,
        max_turns: int | None = None,
        max_sessions: int | None = None,
        ttl_seconds: float | None = None,
    ) -> None:
        self._max_turns = max_turns or settings.history_window
        self._max_sessions = max_sessions or settings.conversation_max_sessions
        self._ttl_seconds = ttl_seconds or settings.conversation_ttl_seconds
        # Insertion order == last-used order (get() re-inserts on access).
        self._sessions: OrderedDict[str, tuple[ConversationMemory, float]] = OrderedDict()
        # /chat handlers run on threadpool threads, so accesses can interleave.
        self._lock = threading.Lock()

    def get(self, conversation_id: str) -> ConversationMemory:
        """Return this conversation's memory, creating it on first use.

        Each call also marks the conversation as just-used, expires idle
        conversations, and enforces the LRU cap.
        """
        now = time.monotonic()
        with self._lock:
            self._evict_expired(now)
            entry = self._sessions.pop(conversation_id, None)
            memory = entry[0] if entry else ConversationMemory(max_turns=self._max_turns)
            self._sessions[conversation_id] = (memory, now)  # (re)insert at MRU end
            while len(self._sessions) > self._max_sessions:
                self._sessions.popitem(last=False)
            return memory

    def reset(self, conversation_id: str) -> None:
        """Drop a conversation's history (used by 'New chat')."""
        with self._lock:
            self._sessions.pop(conversation_id, None)

    def _evict_expired(self, now: float) -> None:
        """Drop conversations idle past the TTL. Caller holds the lock."""
        cutoff = now - self._ttl_seconds
        while self._sessions:
            _, (_, last_used) = next(iter(self._sessions.items()))
            if last_used >= cutoff:
                break  # everything behind this entry is newer
            self._sessions.popitem(last=False)

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)
