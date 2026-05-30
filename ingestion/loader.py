import os
import pdfplumber
from langchain_core.documents import Document
from langsmith import traceable
from utils.logger import get_logger

logger = get_logger(__name__)


def _clean(cell) -> str:
    """Normalize a single table cell."""
    return (cell or "").replace("\n", " ").strip()


def _table_to_markdown(table: list[list]) -> str:
    """
    Render a pdfplumber table as a markdown table.

    The source policy tables use merged cells: the section id (e.g. '1.1a')
    and Band (e.g. '9/10') are written once and span the Lodging/Boarding/DA
    rows beneath them. We forward-fill those leading columns so every rate
    row is self-contained — otherwise a chunk split could orphan a number
    from its band.
    """
    rows = [[_clean(c) for c in row] for row in table]
    rows = [r for r in rows if any(r)]  # drop fully-empty rows
    if not rows:
        return ""

    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]

    # Forward-fill the first two columns (section id + band) down each group.
    last = ["", ""]
    for r in rows:
        for c in range(min(2, width)):
            if r[c]:
                last[c] = r[c]
            else:
                r[c] = last[c]

    header, *body = rows
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    for r in body:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


def _load_one_pdf(path: str) -> list[Document]:
    """
    Load a single PDF, keeping narrative text and rendering tables as
    markdown. Table regions are cropped out of the narrative so numbers
    aren't duplicated in their mangled, run-together form.
    """
    docs: list[Document] = []
    with pdfplumber.open(path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            tables = page.find_tables()
            boxes = [t.bbox for t in tables]

            def outside_tables(obj, boxes=boxes):
                for (x0, top, x1, bottom) in boxes:
                    if (obj["top"] >= top and obj["bottom"] <= bottom
                            and obj["x0"] >= x0 and obj["x1"] <= x1):
                        return False
                return True

            narrative = (page.filter(outside_tables).extract_text() or "").strip()

            parts = [narrative] if narrative else []
            for t in tables:
                md = _table_to_markdown(t.extract())
                if md:
                    parts.append(md)

            content = "\n\n".join(parts).strip()
            if content:
                docs.append(Document(
                    page_content=content,
                    metadata={"source": os.path.basename(path), "page": page_idx},
                ))
    logger.info(f"Loaded {len(docs)} page(s) from '{path}'")
    return docs


@traceable(name="load_documents")
def load_documents(path: str) -> list[Document]:
    """Load a single PDF or every PDF in a directory (table-aware)."""
    if os.path.isdir(path):
        docs: list[Document] = []
        for name in sorted(os.listdir(path)):
            if name.lower().endswith(".pdf"):
                docs.extend(_load_one_pdf(os.path.join(path, name)))
        return docs
    return _load_one_pdf(path)
