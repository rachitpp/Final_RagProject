import html
import logging
import time

import streamlit as st
import streamlit.components.v1 as components

from pipelines.rag_pipeline import RAGPipeline
from ui.constants import ASSISTANT_ACTIONS_HTML, ERROR_HTML, THINKING_HTML
from ui.citations import chipify_citations, sources_html

logger = logging.getLogger(__name__)

# Repaint at most this often while streaming (~20fps cap).
_STREAM_REPAINT_INTERVAL = 0.05


# Example questions for the empty state. Clicking a card fills the chat
# input (handled in client_behaviors.py) so the user can edit before sending.
# Phrased without apostrophes so they sit cleanly in the data-q attribute.
_STARTER_PROMPTS = [
    ("rates", "What is the DA rate for a Category A city?"),
    ("cities", "How are cities classified into categories?"),
    ("lodging", "What are the lodging limits for each band?"),
    ("travel", "Which mode of travel is allowed for each grade?"),
]


def render_empty_state() -> None:
    cards = "".join(
        f"<button class='starter' type='button' data-q=\"{html.escape(q, quote=True)}\">"
        f"<span class='ico'>{label}</span>"
        f"<span class='copy'>{html.escape(q)}</span>"
        f"</button>"
        for label, q in _STARTER_PROMPTS
    )
    st.markdown(
        "<div class='welcome-wrap'>"
        "<div class='eyebrow'>Ready when you are</div>"
        "<div class='welcome-title'>What would you like to know?</div>"
        "<div class='welcome-sub'>"
        "Ask anything about your documents — or start with one of these."
        "</div>"
        f"<div class='starter-grid'>{cards}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def render_user_message(text: str) -> None:
    """Render a user turn as a right-aligned bubble.

    Uses plain st.markdown instead of st.chat_message so the layout stays
    bullet-proof across Streamlit versions that rename internal testids.
    """
    safe = html.escape(text).replace("\n", "<br>")
    st.markdown(
        f"<div class='user-row'>"
        f"<div class='user-label'>◉&nbsp;&nbsp;You</div>"
        f"<div class='user-bubble'>{safe}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def _snap_to_new_question() -> None:
    """Explicit belt-and-suspenders trigger for the snap-to-question scroll.

    The persistent MutationObserver in install_client_behaviors already
    detects new .user-row elements via count growth, so this is redundant
    in the happy path. Emitting it right after render_user_message gives a
    second deterministic trigger that doesn't depend on the observer timing.
    The snap function dedupes via activeSnapRow, so double-fires are no-ops.
    """
    components.html(
        """
        <script>
        (function () {
          const win = window.parent;
          function go() {
            if (typeof win.__ragSnapToLatest === 'function') {
              win.__ragSnapToLatest();
            } else {
              setTimeout(go, 60);
            }
          }
          go();
        })();
        </script>
        """,
        height=0,
    )


def _safe_partial_markdown(text: str) -> str:
    """Close any unclosed code fence so partial renders don't break layout."""
    if text.count("```") % 2 == 1:
        return text + "\n```"
    return text


def _isolate_tables(text: str) -> str:
    """Guarantee a blank line after a markdown table.

    The model often emits its closing citation — e.g. "(domestic travel.pdf,
    p.1)" — on the line directly after the last table row, with no blank line
    between them. Streamlit's markdown parser then folds that line into the
    table block, so the citation chip renders *inside* the table card. A blank
    line terminates the table cleanly, pushing the citation out as its own
    paragraph below the card.

    A "table row" is a line whose first non-space char is "|" and which has at
    least two pipes — the GFM form the model emits. Keying on the leading pipe
    (rather than just counting pipes) avoids false positives on prose that
    happens to contain "|", and we skip lines inside fenced code blocks so a
    code sample containing pipes is never mutated.
    """
    def is_row(s: str) -> bool:
        return s.lstrip().startswith("|") and s.count("|") >= 2

    lines = text.split("\n")
    out: list[str] = []
    in_fence = False
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
        out.append(line)
        if in_fence:
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if nxt is None:
            continue
        if is_row(line) and not is_row(nxt) and nxt.strip() != "":
            out.append("")
    return "\n".join(out)


def _answer_html(text: str) -> str:
    """Assemble the rendered assistant answer: chipified body + sources +
    actions. Centralised so streaming and history render identically."""
    body = _isolate_tables(text)
    return chipify_citations(body) + sources_html(body) + ASSISTANT_ACTIONS_HTML


def stream_with_indicator(pipeline: RAGPipeline, prompt: str) -> str:
    """Stream the answer behind a thinking indicator.

    Returns the full answer text, or "" on failure.
    """
    placeholder = st.empty()
    placeholder.markdown(THINKING_HTML, unsafe_allow_html=True)

    chunks: list[str] = []
    last_paint = 0.0
    try:
        for chunk in pipeline.stream_answer(prompt):
            chunks.append(str(chunk))
            now = time.monotonic()
            if now - last_paint > _STREAM_REPAINT_INTERVAL:
                partial = _safe_partial_markdown("".join(chunks))
                placeholder.markdown(partial + " ▌")
                last_paint = now
    except Exception:
        logger.exception("stream_answer failed for prompt=%r", prompt)
        placeholder.markdown(ERROR_HTML, unsafe_allow_html=True)
        return ""

    full = "".join(chunks).strip()
    if not full:
        logger.info("stream_answer produced no content for prompt=%r", prompt)
        placeholder.markdown(ERROR_HTML, unsafe_allow_html=True)
        return ""

    placeholder.markdown(_answer_html(full), unsafe_allow_html=True)
    return full


def render_history() -> None:
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            render_user_message(msg["content"])
        else:
            with st.chat_message("assistant"):
                st.markdown(_answer_html(msg["content"]), unsafe_allow_html=True)


def handle_user_input(pipeline: RAGPipeline, prompt: str) -> None:
    st.session_state.messages.append({"role": "user", "content": prompt})
    render_user_message(prompt)
    _snap_to_new_question()

    with st.chat_message("assistant"):
        response = stream_with_indicator(pipeline, prompt)

    if response:
        st.session_state.messages.append({"role": "assistant", "content": response})
