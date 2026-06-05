import re
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
    query: str,
    scope: str,
    k: int | None = None,
) -> List[Document]:
    """
    Semantic similarity search, restricted to one scope via a Qdrant metadata
    filter (`metadata.scope == <scope>`). This is where the retriever — not the
    prompt — keeps the domains (domestic | foreign | leave) apart.

    Graceful fallback: if the filtered search returns nothing (e.g. the corpus
    hasn't been re-ingested with scope tags yet), retry unfiltered so the app
    keeps working and self-heals once `create_db.py` is re-run.
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
        docs = store.similarity_search(query, k=k, filter=flt)
    except Exception as e:
        status = getattr(e, "status_code", None)
        content = getattr(e, "content", None)
        logger.warning(
            "Filtered vector search failed (status=%s, detail=%s); retrying "
            "unfiltered. If this persists, re-run create_db.py — the "
            "'metadata.scope' payload index is required for filtering under "
            "Qdrant strict mode.",
            status,
            content or repr(e),
        )
        return store.similarity_search(query, k=k)
    if not docs:
        logger.warning(
            f"No vector hits for scope={scope!r}. The corpus may predate the "
            "scope tag — re-run create_db.py. Falling back to unfiltered search."
        )
        return store.similarity_search(query, k=k)
    return docs


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


def build_bm25_retriever(store: QdrantVectorStore) -> BM25Retriever:
    """Rebuild a single combined BM25 index in-memory from documents already in
    Qdrant. Kept for the sidebar's Library view (which lists every document)."""
    docs = _scroll_all_docs(store)
    retriever = BM25Retriever.from_documents(
        docs, preprocess_func=_bm25_tokenize
    )
    retriever.k = settings.bm25_k
    return retriever


def build_bm25_by_scope(store: QdrantVectorStore) -> Dict[str, BM25Retriever]:
    """
    Build one BM25 index PER scope (domestic | foreign | leave). BM25 is
    in-memory and can't be filtered after the fact like the vector store, so we
    keep a separate index per scope and pick the matching one at query time —
    the keyword-search equivalent of the vector metadata filter. Keying on
    `scope` (always present) means no chunk is silently dropped from the index.
    """
    docs = _scroll_all_docs(store)
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
    vector_query: str,
    store: QdrantVectorStore,
    bm25_by_scope: Dict[str, BM25Retriever],
    scope: str,
) -> List[Document]:
    """
    Hybrid retrieval restricted to ONE scope:
      - BM25 uses the (rewritten) user keywords against the scope's index.
      - Vector search uses the (optionally HYDE-expanded) query, filtered to the
        same scope.
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
    vec_docs = vector_search(store, vector_query, scope)
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
    router decides `scopes`; a cross-domain question unions travel + leave hits."""
    out: List[Document] = []
    for scope in scopes:
        out.extend(
            hybrid_retrieve(bm25_query, vector_query, store, bm25_by_scope, scope)
        )
    merged = _dedupe(out)
    logger.info(f"Multi-scope retrieve {list(scopes)} -> {len(merged)} candidate(s)")
    return merged