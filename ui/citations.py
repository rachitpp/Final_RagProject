import html
import re

# Matches "(file.pdf, p.2)" and the multi-page form "(file.pdf, p.1, p.2)".
#   group 1 = filename — [^(),\n] excludes commas so it stops at the first
#             ", p.N" instead of greedily swallowing it into the name.
#   group 2 = the whole "p.1, p.2, ..." tail; individual page numbers are
#             pulled out of it with _PAGE_RE below.
_CITATION_RE = re.compile(
    r"\(\s*([^(),\n]+?\.[A-Za-z0-9]{1,6})\s*"
    r"((?:,?\s*(?:p\.?|pg\.?|page)\s*\d+)+)"
    r"\s*\)",
    re.IGNORECASE,
)
_PAGE_RE = re.compile(r"\d+")


def _pages(blob: str) -> list[int]:
    """Pull the page numbers out of a citation's 'p.1, p.2' tail, in order."""
    return [int(n) for n in _PAGE_RE.findall(blob)]


def chipify_citations(text: str) -> str:
    """Wrap source citations in styled <span class='cite'> chips."""
    def repl(match: "re.Match[str]") -> str:
        filename = match.group(1).strip()
        pages = _pages(match.group(2))
        label_pages = ", ".join(f"p.{n}" for n in pages)
        # Escape HTML first (the filename comes from model output and the regex
        # permits <, >, & and quotes), THEN neutralise markdown _/* so they
        # don't italicise inside the injected span. Order matters: html.escape
        # leaves _ and * untouched, and our entities are added after escaping
        # so they aren't double-encoded.
        safe = html.escape(filename).replace("_", "&#95;").replace("*", "&#42;")
        attr_doc = html.escape(filename, quote=True)
        # data-page drives the jump-to-source target; use the first page.
        return (
            f"<span class='cite' role='button' tabindex='0' "
            f"data-doc=\"{attr_doc}\" data-page=\"{pages[0]}\" "
            f"title='View this source in the citation list'>"
            f"{safe} · {label_pages}</span>"
        )

    return _CITATION_RE.sub(repl, text)


def sources_html(text: str) -> str:
    """Build the 'N sources' disclosure panel from an answer's citations."""
    pages: "dict[str, set[int]]" = {}
    order: "list[str]" = []
    for match in _CITATION_RE.finditer(text):
        name = match.group(1).strip()
        if name not in pages:
            pages[name] = set()
            order.append(name)
        pages[name].update(_pages(match.group(2)))

    if not order:
        return ""

    # Count distinct source documents — the disclosure renders one row per
    # document (with its pages listed inside), so the toggle label must match
    # that, not the total number of page citations.
    count = len(order)
    noun = "source" if count == 1 else "sources"

    items = []
    for name in order:
        safe = html.escape(name)
        attr_doc = html.escape(name, quote=True)
        pgs = ", ".join(str(p) for p in sorted(pages[name]))
        items.append(
            f"<li class='source-item' data-doc=\"{attr_doc}\">"
            f"<span class='nm'>{safe}</span> "
            f"<span class='pg'>p. {pgs}</span></li>"
        )

    return (
        "\n\n<div class='sources'>"
        "<button class='sources-toggle' type='button' aria-expanded='false'>"
        "<span class='chev' aria-hidden='true'>&#9654;</span> "
        f"{count} {noun}</button>"
        f"<ul class='sources-list'>{''.join(items)}</ul>"
        "</div>"
    )
