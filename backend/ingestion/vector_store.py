import os
from langchain_qdrant import QdrantVectorStore
from langchain_core.documents import Document
from langsmith import traceable
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PayloadSchemaType, VectorParams

from config.settings import settings
from llm.models import get_embedding_model
from utils.logger import get_logger

logger = get_logger(__name__)


def _make_client() -> QdrantClient:
    """Connect to Qdrant Cloud using URL and API key from env."""
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=os.environ.get("QDRANT_API_KEY"),
    )


def _ensure_collection(client: QdrantClient) -> None:
    """
    (Re)create the collection with cosine distance.

    create_db.py is a full rebuild, so we DROP any existing collection
    first. Without this, re-ingesting just appends new chunks on top of
    whatever was there before, leaving stale chunks that pollute retrieval.
    """
    if client.collection_exists(settings.qdrant_collection):
        client.delete_collection(settings.qdrant_collection)
        logger.info(
            f"Dropped existing collection '{settings.qdrant_collection}' "
            "for a clean rebuild"
        )
    client.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config=VectorParams(
            size=settings.qdrant_vector_size,
            distance=Distance.COSINE,
        ),
    )
    logger.info(
        f"Created Qdrant collection '{settings.qdrant_collection}' "
        f"(size={settings.qdrant_vector_size}, distance=cosine)"
    )
    # Index the policy field so retrieval can filter on it. Qdrant Cloud often
    # runs in strict mode, which REJECTS filtering on an unindexed field with an
    # UnexpectedResponse — so this index is what makes the policy filter work,
    # not just a performance nicety. The key is nested because QdrantVectorStore
    # stores metadata under the 'metadata' payload key.
    client.create_payload_index(
        collection_name=settings.qdrant_collection,
        field_name="metadata.policy",
        field_schema=PayloadSchemaType.KEYWORD,
    )
    logger.info("Created payload index on 'metadata.policy' (keyword)")


@traceable(name="create_vector_store")
def create_vector_store(chunks: list[Document]) -> QdrantVectorStore:
    """
    Embed chunks in batches (Vertex caps at ~250/call) and
    persist to Qdrant Cloud using cosine similarity.
    """
    client = _make_client()
    _ensure_collection(client)

    store = QdrantVectorStore(
        client=client,
        collection_name=settings.qdrant_collection,
        embedding=get_embedding_model(),
    )

    batch_size = settings.embedding_batch_size
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        logger.info(
            f"Embedding batch {i // batch_size + 1} ({len(batch)} chunk(s))"
        )
        store.add_documents(batch)

    logger.info(
        f"Persisted {len(chunks)} chunk(s) to collection "
        f"'{settings.qdrant_collection}'"
    )
    return store


def load_vector_store() -> QdrantVectorStore:
    """Connect to the existing Qdrant Cloud collection."""
    client = _make_client()
    return QdrantVectorStore(
        client=client,
        collection_name=settings.qdrant_collection,
        embedding=get_embedding_model(),
    )