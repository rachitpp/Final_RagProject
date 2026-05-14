import os
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_core.documents import Document
from langsmith import traceable
from utils.logger import get_logger

logger = get_logger(__name__)


@traceable(name="load_documents")
def load_documents(path: str) -> list[Document]:
    """Load a single PDF or every PDF in a directory."""
    if os.path.isdir(path):
        loader = DirectoryLoader(path, glob="**/*.pdf", loader_cls=PyPDFLoader)
    else:
        loader = PyPDFLoader(path)
    docs = loader.load()
    logger.info(f"Loaded {len(docs)} page(s) from '{path}'")
    return docs
