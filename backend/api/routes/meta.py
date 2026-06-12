"""Metadata for the UI — the indexed-document Library and the active model.

Groups the pipeline's BM25 docs by source filename and counts distinct pages so
the frontend's sidebar can show "what's indexed". The corpus is frozen for the
life of the process (re-ingesting requires a restart), so the payload is built
once on first request and cached on app.state — previously every request
re-walked all of the BM25 docs.
"""
from fastapi import APIRouter, Depends, Request

from api.deps import get_pipeline
from config.documents import title_for, topic_for
from config.settings import settings
from pipelines.rag_pipeline import RAGPipeline

router = APIRouter()


def build_library_payload(pipeline: RAGPipeline) -> dict:
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
        documents.append(
            {
                "name": name,
                "title": title_for(name),
                "topic": topic_for(name),
                "pages": n,
            }
        )
        if n:
            total_pages += n

    return {
        "documents": documents,
        "total_pages": total_pages,
        "model": settings.llm_model.replace("-", " ").title(),
    }


@router.get("/library")
def library(
    request: Request, pipeline: RAGPipeline = Depends(get_pipeline)
) -> dict:
    payload = getattr(request.app.state, "library_payload", None)
    if payload is None:
        payload = build_library_payload(pipeline)
        request.app.state.library_payload = payload
    return payload
