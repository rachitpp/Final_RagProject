"""Scope isolation is the system's core correctness guarantee, so its failure
modes get pinned by tests: retrieval must FAIL CLOSED (never fall back to an
unfiltered, cross-policy search), untagged corpora must be rejected at boot,
and the query must be embedded exactly once however many scopes are searched."""
from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

from retrieval.retrievers import (
    _dedupe,
    assert_scope_tagged,
    multi_scope_retrieve,
    vector_search,
)


class _FakeStore:
    """Stands in for QdrantVectorStore: counts embeddings, records searches."""

    def __init__(self, hits_by_scope=None, raise_on_search=False):
        self.hits_by_scope = hits_by_scope or {}
        self.raise_on_search = raise_on_search
        self.embed_calls = 0
        self.searched_scopes = []
        outer = self

        class _Emb:
            def embed_query(self, text):
                outer.embed_calls += 1
                return [0.1, 0.2, 0.3]

        self.embeddings = _Emb()

    def similarity_search_by_vector(self, vector, k, filter):
        if self.raise_on_search:
            raise RuntimeError("qdrant down")
        scope = filter.must[0].match.value
        self.searched_scopes.append(scope)
        return list(self.hits_by_scope.get(scope, []))

    # Deliberately NO similarity_search(text) method: if production code ever
    # reintroduces an unfiltered fallback, these tests break with AttributeError.


def _doc(text, scope="domestic"):
    return Document(page_content=text, metadata={"scope": scope})


# ------------------------------------------------------------- vector_search

def test_vector_search_is_scope_filtered():
    store = _FakeStore(hits_by_scope={"foreign": [_doc("usd table", "foreign")]})
    docs = vector_search(store, [0.1], "foreign")
    assert [d.page_content for d in docs] == ["usd table"]
    assert store.searched_scopes == ["foreign"]


def test_vector_search_zero_hits_returns_empty_no_unfiltered_retry():
    """An empty scope is an honest miss, never a cross-scope leak."""
    store = _FakeStore(hits_by_scope={})
    assert vector_search(store, [0.1], "leave") == []
    assert store.searched_scopes == ["leave"]  # exactly one (filtered) search


def test_vector_search_error_fails_closed():
    """A Qdrant error degrades to no vector hits (BM25 still serves) — it must
    NOT retry without the scope filter."""
    store = _FakeStore(raise_on_search=True)
    assert vector_search(store, [0.1], "domestic") == []


# ------------------------------------------------------- multi_scope_retrieve

def _fake_bm25(docs):
    return SimpleNamespace(invoke=lambda q: list(docs))


def test_multi_scope_embeds_query_exactly_once():
    store = _FakeStore(hits_by_scope={
        "domestic": [_doc("inr rates", "domestic")],
        "leave": [_doc("pl rules", "leave")],
    })
    bm25 = {"domestic": _fake_bm25([]), "leave": _fake_bm25([])}
    out = multi_scope_retrieve("q", "q", store, bm25, ("domestic", "leave"))
    assert store.embed_calls == 1  # was once PER SCOPE before the fix
    assert sorted(store.searched_scopes) == ["domestic", "leave"]
    assert {d.page_content for d in out} == {"inr rates", "pl rules"}


def test_multi_scope_unions_and_dedupes_legs():
    shared = _doc("appears in bm25 and vector")
    store = _FakeStore(hits_by_scope={"domestic": [shared]})
    bm25 = {"domestic": _fake_bm25([shared, _doc("bm25 only")])}
    out = multi_scope_retrieve("q", "q", store, bm25, ("domestic",))
    assert [d.page_content for d in out] == [
        "appears in bm25 and vector",
        "bm25 only",
    ]


def test_multi_scope_embedding_failure_degrades_to_bm25_only():
    store = _FakeStore(hits_by_scope={"domestic": [_doc("vector hit")]})
    store.embeddings.embed_query = lambda text: (_ for _ in ()).throw(
        RuntimeError("vertex down")
    )
    bm25 = {"domestic": _fake_bm25([_doc("keyword hit")])}
    out = multi_scope_retrieve("q", "q", store, bm25, ("domestic",))
    assert [d.page_content for d in out] == ["keyword hit"]
    assert store.searched_scopes == []  # vector leg skipped entirely


# ---------------------------------------------------------- boot-time checks

def test_assert_scope_tagged_passes_on_tagged_corpus():
    assert_scope_tagged([_doc("a"), _doc("b", "leave")])  # no raise


def test_assert_scope_tagged_rejects_untagged_corpus():
    docs = [_doc("a"), Document(page_content="legacy chunk", metadata={})]
    with pytest.raises(RuntimeError, match="create_db.py"):
        assert_scope_tagged(docs)


def test_dedupe_preserves_first_occurrence_order():
    docs = [_doc("one"), _doc("two"), _doc("one")]
    assert [d.page_content for d in _dedupe(docs)] == ["one", "two"]
