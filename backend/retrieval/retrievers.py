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
    policy: str,
    k: int | None = None,
) -> List[Document]:
    """
    Semantic similarity search, restricted to one policy via a Qdrant metadata
    filter (`metadata.policy == <policy>`). This is where the retriever — not
    the prompt — keeps Domestic and Foreign body content apart.

    Graceful fallback: if the filtered search returns nothing (e.g. the corpus
    hasn't been re-ingested with policy tags yet), retry unfiltered so the app
    keeps working and self-heals once `create_db.py` is re-run.
    """
    k = k or settings.vector_k
    flt = qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="metadata.policy",
                match=qmodels.MatchValue(value=policy),
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
            "'metadata.policy' payload index is required for filtering under "
            "Qdrant strict mode.",
            status,
            content or repr(e),
        )
        return store.similarity_search(query, k=k)
    if not docs:
        logger.warning(
            f"No vector hits for policy={policy!r}. The corpus may predate the "
            "policy tag — re-run create_db.py. Falling back to unfiltered search."
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


def build_bm25_by_policy(store: QdrantVectorStore) -> Dict[str, BM25Retriever]:
    """
    Build one BM25 index PER policy. BM25 is in-memory and can't be filtered
    after the fact like the vector store, so we keep a separate index per policy
    and pick the matching one at query time — the keyword-search equivalent of
    the vector metadata filter.
    """
    docs = _scroll_all_docs(store)
    grouped: Dict[str, List[Document]] = {}
    for d in docs:
        policy = (d.metadata or {}).get("policy")
        if not policy:
            continue
        grouped.setdefault(policy, []).append(d)

    retrievers: Dict[str, BM25Retriever] = {}
    for policy, group in grouped.items():
        r = BM25Retriever.from_documents(group, preprocess_func=_bm25_tokenize)
        r.k = settings.bm25_k
        retrievers[policy] = r
    logger.info(f"Built BM25 indexes for policies: {sorted(retrievers)}")
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
    bm25_by_policy: Dict[str, BM25Retriever],
    policy: str,
) -> List[Document]:
    """
    Hybrid retrieval restricted to one policy:
      - BM25 uses the (rewritten) user keywords against the policy's index.
      - Vector search uses the (optionally HYDE-expanded) query, filtered to the
        same policy.
    Results are concatenated + de-duped. Both legs are policy-scoped, so a
    Domestic query never surfaces Foreign body chunks (and vice versa).
    """
    bm25 = bm25_by_policy.get(policy)
    if bm25 is not None:
        bm25_docs = bm25.invoke(bm25_query)
    else:
        logger.warning(
            f"No BM25 index for policy={policy!r} (re-ingest needed?); "
            "skipping the keyword leg for this query."
        )
        bm25_docs = []
    vec_docs = vector_search(store, vector_query, policy)
    logger.info(
        f"Retrieved BM25={len(bm25_docs)}, Vector={len(vec_docs)} "
        f"(policy={policy})"
    )
    merged = _dedupe(bm25_docs + vec_docs)
    logger.info(f"After dedupe: {len(merged)} candidate(s)")
    return merged