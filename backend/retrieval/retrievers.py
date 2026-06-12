import re
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List
from langchain_qdrant import QdrantVectorStore
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langsmith import traceable
from qdrant_client.http import models as qmodels
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


def _bm25_tokenize(text: str) -> List[str]:
    """
    Lowercase + split on non-alphanumerics.

    BM25Retriever's default tokenizer is a bare str.split(), so tokens keep
    their punctuation and case: 'Pune.' never matches a query token 'pune'.
    Our tables are full of punctuation (markdown pipes, trailing periods),
    so we normalize both sides with this.
    """
    return re.findall(r"[a-z0-9]+", text.lower())


def vector_search(
    store: QdrantVectorStore,
    query_vector: List[float],
    scope: str,
    k: int | None = None,
) -> List[Document]:
    """
    Semantic similarity search, restricted to one scope via a Qdrant metadata
    filter (`metadata.scope == <scope>`). This is where the retriever — not the
    prompt — keeps the domains (domestic | foreign | leave) apart.

    Takes a precomputed query embedding (the caller embeds ONCE per query and
    reuses it across scopes — `similarity_search(text)` re-embedded the same
    string on every scope leg, one paid Vertex round-trip each).

    FAIL CLOSED, never sideways: scope isolation is this system's core
    correctness guarantee (the two travel policies reuse the same A/B/C labels
    and "DA" in different currencies), so there is NO unfiltered fallback. Zero
    hits means this scope genuinely has nothing — that flows to the prompt's
    honest "I could not find the answer" behaviour. A transient Qdrant error
    degrades to the (still scope-isolated) BM25 leg for this query rather than
    leaking cross-policy chunks. Untagged corpora are rejected at startup
    instead (assert_scope_tagged), not papered over here.
    """
    k = k or settings.vector_k
    flt = qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="metadata.scope",
                match=qmodels.MatchValue(value=scope),
            )
        ]
    )
    try:
        return store.similarity_search_by_vector(query_vector, k=k, filter=flt)
    except Exception as e:
        status = getattr(e, "status_code", None)
        content = getattr(e, "content", None)
        logger.error(
            "Scoped vector search failed (scope=%r, status=%s, detail=%s); "
            "skipping the vector leg for this query (BM25 still serves). If "
            "this persists, re-run create_db.py — the 'metadata.scope' payload "
            "index is required for filtering under Qdrant strict mode.",
            scope,
            status,
            content or repr(e),
        )
        return []


def assert_scope_tagged(docs: List[Document]) -> None:
    """
    Startup invariant check: every chunk must carry a `scope` tag, because all
    retrieval (the vector filter AND the per-scope BM25 indexes) isolates on it.
    The startup scroll already has every chunk in hand, so validating here is
    free — and failing the boot is strictly better than the old behaviour of
    silently retrying unfiltered per query, which leaked cross-policy chunks.
    """
    untagged = sum(1 for d in docs if not (d.metadata or {}).get("scope"))
    if untagged:
        raise RuntimeError(
            f"{untagged} of {len(docs)} chunk(s) have no 'scope' metadata tag. "
            "The corpus predates scope-tagged ingestion; scope-isolated "
            "retrieval cannot work against it. Re-run create_db.py to rebuild "
            "the collection."
        )


def _scroll_all_docs(store: QdrantVectorStore) -> List[Document]:
    """
    Pull every stored chunk back out of Qdrant via scroll().
    QdrantVectorStore stores page_content under `content_payload_key`
    and metadata under `metadata_payload_key` (defaults: 'page_content'
    and 'metadata').
    """
    docs: List[Document] = []
    offset = None
    content_key = store.content_payload_key
    metadata_key = store.metadata_payload_key

    while True:
        points, offset = store.client.scroll(
            collection_name=store.collection_name,
            limit=256,
            with_payload=True,
            with_vectors=False,
            offset=offset,
        )
        for p in points:
            payload = p.payload or {}
            docs.append(Document(
                page_content=payload.get(content_key, ""),
                metadata=payload.get(metadata_key, {}) or {},
            ))
        if offset is None:
            break
    return docs


def build_bm25_retriever(docs: List[Document]) -> BM25Retriever:
    """Build a single combined BM25 index in-memory from already-scrolled chunks
    (the caller scrolls Qdrant ONCE and feeds every startup consumer — see
    RAGPipeline.__init__). Kept for the sidebar's Library view."""
    retriever = BM25Retriever.from_documents(
        docs, preprocess_func=_bm25_tokenize
    )
    retriever.k = settings.bm25_k
    return retriever


def build_bm25_by_scope(docs: List[Document]) -> Dict[str, BM25Retriever]:
    """
    Build one BM25 index PER scope (domestic | foreign | leave) from
    already-scrolled chunks. BM25 is in-memory and can't be filtered after the
    fact like the vector store, so we keep a separate index per scope and pick
    the matching one at query time — the keyword-search equivalent of the
    vector metadata filter. Keying on `scope` (always present) means no chunk
    is silently dropped from the index.
    """
    grouped: Dict[str, List[Document]] = {}
    for d in docs:
        scope = (d.metadata or {}).get("scope")
        if not scope:
            logger.warning(
                "Chunk with no 'scope' skipped from BM25 (re-ingest needed)."
            )
            continue
        grouped.setdefault(scope, []).append(d)

    retrievers: Dict[str, BM25Retriever] = {}
    for scope, group in grouped.items():
        r = BM25Retriever.from_documents(group, preprocess_func=_bm25_tokenize)
        r.k = settings.bm25_k
        retrievers[scope] = r
    logger.info(f"Built BM25 indexes for scopes: {sorted(retrievers)}")
    return retrievers


def _dedupe(docs: List[Document]) -> List[Document]:
    """Drop duplicates by exact page_content, preserving order."""
    seen, out = set(), []
    for d in docs:
        if d.page_content not in seen:
            seen.add(d.page_content)
            out.append(d)
    return out


@traceable(name="hybrid_retrieve")
def hybrid_retrieve(
    bm25_query: str,
    query_vector: List[float] | None,
    store: QdrantVectorStore,
    bm25_by_scope: Dict[str, BM25Retriever],
    scope: str,
) -> List[Document]:
    """
    Hybrid retrieval restricted to ONE scope:
      - BM25 uses the (rewritten) user keywords against the scope's index.
      - Vector search uses the precomputed query embedding, filtered to the
        same scope (None when embedding failed -> keyword-only this query).
    Results are concatenated + de-duped. Both legs are scope-scoped, so a leave
    query never surfaces travel body chunks (and vice versa).
    """
    bm25 = bm25_by_scope.get(scope)
    if bm25 is not None:
        bm25_docs = bm25.invoke(bm25_query)
    else:
        logger.warning(
            f"No BM25 index for scope={scope!r} (re-ingest needed?); "
            "skipping the keyword leg for this scope."
        )
        bm25_docs = []
    vec_docs = (
        vector_search(store, query_vector, scope) if query_vector is not None else []
    )
    logger.info(
        f"Retrieved BM25={len(bm25_docs)}, Vector={len(vec_docs)} (scope={scope})"
    )
    return _dedupe(bm25_docs + vec_docs)


@traceable(name="multi_scope_retrieve")
def multi_scope_retrieve(
    bm25_query: str,
    vector_query: str,
    store: QdrantVectorStore,
    bm25_by_scope: Dict[str, BM25Retriever],
    scopes,
) -> List[Document]:
    """Run hybrid retrieval once per scope and union + dedupe across them. The
    router decides `scopes`; a cross-domain question unions travel + leave hits.

    The query is embedded ONCE here and the vector is shared by every scope leg
    (previously each leg re-embedded the identical string — one extra Vertex
    round-trip per scope). Multi-scope legs run concurrently: each is an
    independent network call against the same read-only indexes.
    """
    scopes = list(scopes)
    try:
        query_vector = store.embeddings.embed_query(vector_query)
    except Exception as e:
        # Fail closed to the scope-isolated BM25 legs, never to noise.
        logger.error(f"Query embedding failed ({e!r}); keyword-only this query.")
        query_vector = None

    def _leg(scope: str) -> List[Document]:
        return hybrid_retrieve(bm25_query, query_vector, store, bm25_by_scope, scope)

    if len(scopes) <= 1:
        per_scope = [_leg(s) for s in scopes]
    else:
        with ThreadPoolExecutor(max_workers=len(scopes)) as pool:
            per_scope = list(pool.map(_leg, scopes))

    out: List[Document] = []
    for docs in per_scope:
        out.extend(docs)
    merged = _dedupe(out)
    logger.info(f"Multi-scope retrieve {scopes} -> {len(merged)} candidate(s)")
    return merged