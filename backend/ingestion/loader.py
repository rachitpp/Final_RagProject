import os
import re
import pdfplumber
from langchain_core.documents import Document
from langsmith import traceable
from utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Page chrome. The policies are an HTML page exported to PDF, so every page
# repeats the same web furniture: a "Welcome <date> Logout..." header, a
# "Policy • Annexure • Change Password" nav strip, and a footer URL + "Page X
# of Y" / copyright line. None of it is policy content — left in, it pollutes
# every embedding and BM25 signal and even gets misread as a table row. The
# loader's job is to emit policy text, so we strip it here at the source.
# ---------------------------------------------------------------------------
_CHROME_RE = re.compile(
    r"Welcome\s+\d{1,2}/\d{1,2}/\d{2,4},?\s*\d{1,2}:\d{2}\s*[AP]\.?M\.?"
    r"|Logout\s+You are Logged in as\s*:?\s*\d+"
    r"|You are Logged in as\s*:?\s*\d+"
    r"|•\s*Policy\s*•\s*Annexure\s*•\s*Change Password"
    r"|Change Password"
    r"|©\s*Copyright.*?Reserved"
    r"|Website Designed & Developed by\s*:?\s*iNET Business Hub"
    r"|https?://\S+"
    r"|Page\s+\d+\s+of\s+\d+",
    re.IGNORECASE,
)

# A bare date/time stamp is the fingerprint of a chrome row that pdfplumber
# swept into a table (e.g. "| elcome | ... | 30/04/26, 1:55 A |"), where the
# leading 'W' was clipped so the word-based pattern above won't catch it.
_DATESTAMP_RE = re.compile(r"\d{1,2}/\d{1,2}/\d{2,4}")

# Real table headers in this corpus. Used to decide whether a table at the
# top of a page is a NEW table or the tail of one continued from the page
# before (which would have no header of its own).
_HEADER_TOKENS = (
    "mode of travel",
    "categories / countries",
    "classification of cities",
    "countries",
)


def _strip_chrome(text: str) -> str:
    """Remove page furniture from extracted narrative text."""
    text = _CHROME_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _clean(cell) -> str:
    """Normalize a single table cell."""
    return (cell or "").replace("\n", " ").strip()


def _is_chrome_row(cells: list[str]) -> bool:
    """True if a table row is actually swept-in page chrome, not data."""
    joined = " ".join(c for c in cells if c).strip()
    if not joined:
        return True
    low = joined.lower()
    if _CHROME_RE.search(joined) or _DATESTAMP_RE.search(joined):
        return True
    if re.search(r"page\s+\d+\s+of", low):
        return True
    # The footer URL is often broken across cells ("tps://www", ".dcminfotec",
    # "fid=30"), so the https?:// pattern misses it — match the fragments too.
    if "://" in low or "dcminfotec" in low or "fid=" in low or "policy-de" in low:
        return True
    return False


def _extract_rows(table: list[list]) -> list[list[str]]:
    """
    Clean a pdfplumber table into uniform-width rows, dropping empty and
    chrome rows. Forward-fill is deferred until after any cross-page merge so
    a band label on page N flows into its continuation rows on page N+1.
    """
    rows = [[_clean(c) for c in row] for row in table]
    rows = [r for r in rows if any(r) and not _is_chrome_row(r)]
    if not rows:
        return []
    width = max(len(r) for r in rows)
    return [r + [""] * (width - len(r)) for r in rows]


def _forward_fill(rows: list[list[str]]) -> None:
    """
    Forward-fill the first two columns (section id + band) down each group, in
    place. The source tables write these once and span the Lodging/Boarding/DA
    sub-rows beneath, so without this every rate row but the first is orphaned
    from its band.
    """
    if not rows:
        return
    width = len(rows[0])
    last = ["", ""]
    for r in rows:
        for c in range(min(2, width)):
            if r[c]:
                last[c] = r[c]
            else:
                r[c] = last[c]


def _looks_like_header(row: list[str]) -> bool:
    joined = " ".join(row).lower()
    return any(tok in joined for tok in _HEADER_TOKENS)


def _render_markdown(rows: list[list[str]]) -> str:
    """Render cleaned rows as a markdown table (row 0 = header)."""
    if not rows:
        return ""
    width = len(rows[0])
    header, body = rows[0], rows[1:]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    for r in body:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


def _policy_for(path: str) -> str:
    """Derive the policy tag from the filename so retrieval can isolate one
    policy per query. 'foreign.pdf' -> 'foreign'; everything else (e.g.
    'domestic travel.pdf') -> 'domestic'. This is the single structural fact
    that lets the retriever — not the prompt — keep the two policies apart."""
    name = os.path.basename(path).lower()
    if "foreign" in name or "overseas" in name:
        return "foreign"
    return "domestic"


def _load_one_pdf(path: str) -> list[Document]:
    """
    Load a single PDF, keeping narrative text and rendering tables as markdown.
    Table regions are cropped out of the narrative so numbers aren't duplicated
    in their mangled form, page chrome is stripped, and a table that breaks
    across a page boundary (e.g. the band rate matrix) is stitched back into a
    single self-describing table rather than left as a headerless fragment.
    """
    page_parts: list[tuple[int, str, list[list[list[str]]]]] = []
    prev_page_last_table: list[list[str]] | None = None

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

            narrative = _strip_chrome(
                page.filter(outside_tables).extract_text() or ""
            )

            page_tables = [_extract_rows(t.extract()) for t in tables]
            page_tables = [r for r in page_tables if r]

            kept_tables: list[list[list[str]]] = []
            for i, rows in enumerate(page_tables):
                is_continuation = (
                    i == 0
                    and prev_page_last_table is not None
                    and len(rows[0]) == len(prev_page_last_table[0])
                    and not _looks_like_header(rows[0])
                )
                if is_continuation:
                    # Tail of the previous page's table: append its rows to that
                    # same table object (it lives in an earlier page's part).
                    prev_page_last_table.extend(rows)
                else:
                    kept_tables.append(rows)
                    prev_page_last_table = rows

            page_parts.append((page_idx, narrative, kept_tables))

    docs: list[Document] = []
    for page_idx, narrative, tables in page_parts:
        parts = [narrative] if narrative else []
        for rows in tables:
            _forward_fill(rows)
            md = _render_markdown(rows)
            if md:
                parts.append(md)
        content = "\n\n".join(parts).strip()
        if content:
            docs.append(Document(
                page_content=content,
                metadata={
                    "source": os.path.basename(path),
                    # +1 so this is the 1-based human page number, not the
                    # 0-based enumerate index. The raw index used to leak into
                    # citations as "p.0", "p.1" (one low on every page).
                    "page": page_idx + 1,
                    "policy": _policy_for(path),
                },
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
