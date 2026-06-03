from langsmith import traceable
from ingestion.loader import load_documents
from ingestion.splitter import split_documents
from ingestion.vector_store import create_vector_store
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


@traceable(name="ingestion_pipeline")
def run_ingestion(
    pdf_path: str | None = None,
) -> None:
    """Load → split → embed → persist."""
    pdf_path = pdf_path or settings.pdf_path

    docs = load_documents(pdf_path)
    chunks = split_documents(docs)
    store = create_vector_store(chunks)

    count = store.client.count(
        collection_name=settings.qdrant_collection,
        exact=True,
    ).count
    logger.info(f"Qdrant now holds {count} document(s).")