from typing import List
from langchain_qdrant import QdrantVectorStore
from langchain_core.documents import Document
from qdrant_client.http import models as qmodels
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


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
    logger.info(f"Retrieved Vector={len(docs)} (policy={policy})")
    return docs


def _scroll_all_docs(store: QdrantVectorStore) -> List[Document]:
    """
    Pull every stored chunk back out of Qdrant via scroll().
    QdrantVectorStore stores page_content under `content_payload_key`
    and metadata under `metadata_payload_key` (defaults: 'page_content'
    and 'metadata'). Used to resolve the pinned reference tables at startup
    and to populate the sidebar's Library view.
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
