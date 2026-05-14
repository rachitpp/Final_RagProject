from langchain_core.documents import Document


def format_docs(docs: list[Document]) -> str:
    """
    Render docs into a single context string with provenance tags.
    Includes the rerank score when available so the LLM (and reader)
    can see which chunks were most confident.
    """
    parts = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page", "?")
        score = doc.metadata.get("rerank_score")
        score_str = f" | score={score}" if score is not None else ""
        parts.append(
            f"[Chunk {i} | {source}, p.{page}{score_str}]\n{doc.page_content}"
        )
    return "\n\n---\n\n".join(parts)
