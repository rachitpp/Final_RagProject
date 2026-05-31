import html
import logging

import streamlit as st

from pipelines.rag_pipeline import RAGPipeline
from ui.session import reset_conversation

logger = logging.getLogger(__name__)


def _list_indexed_documents(pipeline: RAGPipeline) -> "tuple[list[dict], int]":
    """Return (documents, total_pages) from the pipeline's BM25 index.

    The pipeline holds a single combined BM25Retriever (pipeline.bm25) whose
    .docs list carries every chunk, each tagged with metadata {"source", "page"}
    by the loader. We group those by source filename and count distinct pages.
    """
    bm25 = getattr(pipeline, "bm25", None)
    docs = getattr(bm25, "docs", None)
    if not isinstance(docs, list):
        return [], 0

    pages_by_source: "dict[str, set]" = {}
    for d in docs:
        meta = getattr(d, "metadata", None) or {}
        name = meta.get("source")
        if not name:
            continue
        page = meta.get("page")
        bucket = pages_by_source.setdefault(name, set())
        if page is not None:
            bucket.add(page)

    if not pages_by_source:
        return [], 0

    normalized: "list[dict]" = []
    total_pages = 0
    for name in sorted(pages_by_source):
        page_count = len(pages_by_source[name]) or None
        normalized.append({"name": name, "pages": page_count})
        if page_count:
            total_pages += page_count
    return normalized, total_pages


def render_sidebar(pipeline: RAGPipeline) -> None:
    with st.sidebar:
        st.markdown(
            "<div class='sidebar-brand'>RAG Assistant</div>"
            "<div class='sidebar-sub'>"
            "Ask questions across your indexed documents."
            "</div>"
            "<div class='sidebar-rule'></div>",
            unsafe_allow_html=True,
        )
        if st.button("New chat", use_container_width=True, type="secondary"):
            reset_conversation(pipeline)
            st.rerun()

        docs, total_pages = _list_indexed_documents(pipeline)
        if docs:
            doc_count = len(docs)
            doc_noun = "document" if doc_count == 1 else "documents"
            page_meta = f" · {total_pages:,} pages" if total_pages else ""
            items_html: "list[str]" = []
            for d in docs[:40]:
                safe_name = html.escape(d["name"])
                pages = d.get("pages")
                meta_html = (
                    f"<span class='lib-meta'>{pages} pp.</span>"
                    if isinstance(pages, int)
                    else ""
                )
                items_html.append(
                    f"<li class='lib-doc' title='{safe_name}'>"
                    f"<span class='lib-name'>{safe_name}</span>{meta_html}</li>"
                )
            overflow_html = (
                f"<li class='lib-more'>+ {len(docs) - 40} more</li>"
                if len(docs) > 40
                else ""
            )
            st.markdown(
                "<div class='library'>"
                "<div class='lib-head'>"
                "<span class='lib-label'>Library</span>"
                f"<span class='lib-count'>{doc_count} {doc_noun}{page_meta}</span>"
                "</div>"
                f"<ul class='lib-list'>{''.join(items_html)}{overflow_html}</ul>"
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div class='library library--empty'>"
                "<div class='lib-head'>"
                "<span class='lib-label'>Library</span>"
                "<span class='lib-count'>No documents detected</span>"
                "</div>"
                "<div class='lib-empty-note'>"
                "Add documents to your index, then reload — they’ll "
                "appear here automatically."
                "</div>"
                "</div>",
                unsafe_allow_html=True,
            )
