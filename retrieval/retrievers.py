from typing import List
from langchain_qdrant import QdrantVectorStore
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langsmith import traceable
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


def build_vector_retriever(store: QdrantVectorStore):
    """Vector retriever with MMR for diversity."""
    return store.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": settings.vector_k,
            "fetch_k": settings.vector_fetch_k,
            "lambda_mult": settings.vector_mmr_lambda,
        },
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


def build_bm25_retriever(store: QdrantVectorStore) -> BM25Retriever:
    """Rebuild a BM25 index in-memory from documents already in Qdrant."""
    docs = _scroll_all_docs(store)
    retriever = BM25Retriever.from_documents(docs)
    retriever.k = settings.bm25_k
    return retriever


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
    bm25_retriever: BM25Retriever,
    vector_retriever,
) -> List[Document]:
    """
    BM25 uses the (rewritten) user keywords.
    Vector MMR uses the HYDE passage — a richer semantic query.

    We concatenate + dedupe; the cross-encoder does final ranking,
    so we don't need to score-fuse here.
    """
    bm25_docs = bm25_retriever.invoke(bm25_query)
    vec_docs = vector_retriever.invoke(vector_query)
    logger.info(f"Retrieved BM25={len(bm25_docs)}, Vector={len(vec_docs)}")
    merged = _dedupe(bm25_docs + vec_docs)
    logger.info(f"After dedupe: {len(merged)} candidate(s)")
    return merged