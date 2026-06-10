"""ConversationStore bounds: LRU cap + idle TTL.

Pure in-process tests — no app, no DB. Time is faked by monkeypatching
time.monotonic as seen by conversation.store, so TTL expiry is deterministic.
"""
import conversation.store as store_module
from conversation.store import ConversationStore


def test_get_preserves_history_across_calls():
    store = ConversationStore(max_turns=4, max_sessions=10, ttl_seconds=1000)
    store.get("a").add("q1", "a1")
    assert store.get("a").turns() == [("q1", "a1")]


def test_lru_cap_evicts_least_recently_used():
    store = ConversationStore(max_turns=4, max_sessions=2, ttl_seconds=1000)
    store.get("a").add("qa", "ra")
    store.get("b")
    store.get("a")          # touch a -> b is now least recently used
    store.get("c")          # over cap -> evicts b, not a
    assert store.get("a").turns() == [("qa", "ra")]  # survived
    assert len(store) == 2  # a + c (this get of "a" re-used the live entry)


def test_ttl_expires_idle_conversations(monkeypatch):
    clock = {"now": 1000.0}
    monkeypatch.setattr(store_module.time, "monotonic", lambda: clock["now"])

    store = ConversationStore(max_turns=4, max_sessions=10, ttl_seconds=60)
    store.get("old").add("q", "r")
    clock["now"] += 30
    store.get("fresh")
    clock["now"] += 45      # old idle 75s (expired), fresh idle 45s (alive)
    store.get("fresh")
    assert len(store) == 1  # 'old' swept
    assert store.get("old").turns() == []  # comes back empty, not stale


def test_reset_drops_only_that_conversation():
    store = ConversationStore(max_turns=4, max_sessions=10, ttl_seconds=1000)
    store.get("a").add("q", "r")
    store.get("b").add("q", "r")
    store.reset("a")
    assert store.get("a").turns() == []
    assert store.get("b").turns() == [("q", "r")]
