"""Chat route: auth-gated, forwards the caller's band, namespaces memory by user.

The heavy RAGPipeline and ConversationStore are replaced with fakes via
dependency_overrides, so these tests exercise the route wiring (Step 8) without
Qdrant/Vertex.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import get_pipeline, get_sessions
from api.routes import auth, chat


class _FakeMemory:
    def __init__(self):
        self._turns = []

    def turns(self):
        return self._turns

    def add(self, user, assistant):
        self._turns.append((user, assistant))


class _FakeSessions:
    def __init__(self):
        self.store = {}
        self.last_key = None

    def get(self, key):
        self.last_key = key
        return self.store.setdefault(key, _FakeMemory())

    def reset(self, key):
        self.last_key = key
        self.store.pop(key, None)


class _FakePipeline:
    def __init__(self):
        self.seen_band = None

    def stream_answer(self, query, history, user_profile=None):
        self.seen_band = getattr(user_profile, "band", None)
        yield f"band={self.seen_band}"


@pytest.fixture
def ctx():
    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(chat.router)
    pipe, sess = _FakePipeline(), _FakeSessions()
    app.dependency_overrides[get_pipeline] = lambda: pipe
    app.dependency_overrides[get_sessions] = lambda: sess
    return TestClient(app), pipe, sess


def _token(client):
    return client.post(
        "/auth/activate",
        json={"employee_id": "E105", "email": "kunal@company.com", "password": "kunalpass1"},
    ).json()["access_token"]


def test_chat_requires_auth(ctx):
    client, _, _ = ctx
    assert client.post("/chat", json={"question": "hi", "conversation_id": "c1"}).status_code == 401


def test_chat_forwards_band_and_namespaces_session(ctx):
    client, pipe, sess = ctx
    tok = _token(client)
    r = client.post(
        "/chat",
        json={"question": "da?", "conversation_id": "c1"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200
    assert r.text == "band=10"          # band from DB reached the pipeline
    assert pipe.seen_band == 10
    assert sess.last_key == "E105:c1"   # memory key namespaced by employee_id


def test_chat_rate_limited_per_user(ctx, monkeypatch):
    """The N+1th /chat inside the window gets 429 + Retry-After; /reset is exempt."""
    from api.ratelimit import chat_limiter

    monkeypatch.setattr(chat_limiter, "max_attempts", 3)
    client, _, _ = ctx
    tok = _token(client)
    headers = {"Authorization": f"Bearer {tok}"}
    body = {"question": "da?", "conversation_id": "c1"}

    for _ in range(3):
        assert client.post("/chat", json=body, headers=headers).status_code == 200
    r = client.post("/chat", json=body, headers=headers)
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    # Cheap, unmetered endpoints are not throttled by the chat limiter.
    assert client.post("/reset", json={"conversation_id": "c1"}, headers=headers).status_code == 200


def test_reset_requires_auth_and_namespaces(ctx):
    client, _, sess = ctx
    assert client.post("/reset", json={"conversation_id": "c1"}).status_code == 401
    tok = _token(client)
    client.post("/reset", json={"conversation_id": "c1"}, headers={"Authorization": f"Bearer {tok}"})
    assert sess.last_key == "E105:c1"
