"""Metadata for the UI — the indexed-document Library and the active model.

Groups the pipeline's BM25 docs by source filename and counts distinct pages so
the frontend's sidebar can show "what's indexed".
"""
from fastapi import APIRouter, Depends

from api.deps import get_pipeline
from config.settings import settings
from pipelines.rag_pipeline import RAGPipeline

router = APIRouter()


@router.get("/library")
def library(pipeline: RAGPipeline = Depends(get_pipeline)) -> dict:
    docs = getattr(getattr(pipeline, "bm25", None), "docs", None) or []

    pages_by_source: dict[str, set] = {}
    for d in docs:
        meta = getattr(d, "metadata", None) or {}
        name = meta.get("source")
        if not name:
            continue
        bucket = pages_by_source.setdefault(name, set())
        page = meta.get("page")
        if page is not None:
            bucket.add(page)

    documents = []
    total_pages = 0
    for name in sorted(pages_by_source):
        n = len(pages_by_source[name]) or None
        documents.append({"name": name, "pages": n})
        if n:
            total_pages += n

    return {
        "documents": documents,
        "total_pages": total_pages,
        "model": settings.llm_model.replace("-", " ").title(),
    }
