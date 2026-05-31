from langchain_core.documents import Document


def format_docs(docs: list[Document]) -> str:
    """
    Render docs into a single context string with provenance tags
    (source + page) so the model can cite section/page accurately.
    """
    parts = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page", "?")
        parts.append(
            f"[Chunk {i} | {source}, p.{page}]\n{doc.page_content}"
        )
    return "\n\n---\n\n".join(parts)
