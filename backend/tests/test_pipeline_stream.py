"""stream_answer behaviour that doesn't need Qdrant/Vertex: the honest
router-failure reply, the off-topic clarify reply, and the per-round prose
buffering (a tool round's prose — whether a short preamble or a complete
premature answer — must never reach the user; only a tool-free round's
prose does).

RAGPipeline is built without __init__ (no vector store); _retrieve and the
LLM are replaced with fakes. Chunks are real AIMessageChunks so the gathered
+= chunk accumulation and .tool_calls parsing run the production code paths.
"""
import json
from langchain_core.messages import AIMessageChunk

from pipelines.rag_pipeline import RAGPipeline
from retrieval.classify import Route
from langchain_core.documents import Document

_DOC = Document(
    page_content="Band 9/10 lodging: 4000/day (Category A).",
    metadata={"source": "domestic travel.pdf", "page": 2},
)


class _FakeLLM:
    """Replays scripted rounds of chunks; bind_tools returns itself."""

    def __init__(self, rounds):
        self.rounds = list(rounds)

    def bind_tools(self, tools):
        return self

    def stream(self, messages):
        return iter(self.rounds.pop(0))


def _pipe(route, rounds=None):
    pipe = RAGPipeline.__new__(RAGPipeline)
    docs = [_DOC] if route.scopes else []
    pipe._retrieve = lambda q, h: (docs, q, route)
    pipe.pinned = {}
    if rounds is not None:
        pipe.llm = _FakeLLM(rounds)
        from llm.tools import compute_entitlement, compute_leave_ledger
        pipe._cap_tools = {
            "calculator": compute_entitlement,
            "leave_ledger": compute_leave_ledger,
        }
        pipe._tools = {t.name: t for t in pipe._cap_tools.values()}
    return pipe


def _tool_call_chunk():
    return AIMessageChunk(
        content="",
        tool_call_chunks=[{
            "name": "compute_entitlement",
            "args": json.dumps({"line_items": []}),
            "id": "call-1",
            "index": 0,
            "type": "tool_call_chunk",
        }],
    )


_DOMESTIC = Route(scopes=("domestic",), trip_type="domestic", assumed=False)


def test_router_error_yields_honest_retry_message():
    pipe = _pipe(Route(scopes=(), trip_type=None, assumed=False, error=True))
    out = "".join(pipe.stream_answer("how many sick days?"))
    assert "try asking it again" in out
    # And no fabricated policy content alongside it.
    assert "Domestic" not in out


def test_off_topic_yields_clarify_message():
    pipe = _pipe(Route(scopes=(), trip_type=None, assumed=False))
    out = "".join(pipe.stream_answer("hello!"))
    assert "rephrase" in out


class _Profile:
    """Satisfies the pipeline's UserContext duck type."""
    def __init__(self, name="Rahul Sharma", band=9):
        self.name = name
        self.band = band


def test_off_topic_first_turn_greets_by_first_name():
    pipe = _pipe(Route(scopes=(), trip_type=None, assumed=False))
    out = "".join(pipe.stream_answer("hello!", user_profile=_Profile()))
    assert out.startswith("Hi Rahul! ")
    assert "rephrase" in out


def test_off_topic_later_turn_does_not_greet():
    pipe = _pipe(Route(scopes=(), trip_type=None, assumed=False))
    history = [("lodging in Pune?", "**...**")]
    out = "".join(pipe.stream_answer("hello!", history, user_profile=_Profile()))
    assert "Hi Rahul" not in out
    assert "rephrase" in out


def test_personalization_reaches_prompt_only_when_named():
    """First turn with a profile -> the system prompt carries the first name
    and the greeting instruction; anonymous -> the slot stays empty."""
    captured = {}

    class _SpyLLM(_FakeLLM):
        def stream(self, messages):
            captured["system"] = messages[0].content
            return super().stream(messages)

    text = "**Yes.** (domestic travel.pdf, p.2)"
    pipe = _pipe(_DOMESTIC, [[AIMessageChunk(content=text)]])
    pipe.llm = _SpyLLM([[AIMessageChunk(content=text)]])
    "".join(pipe.stream_answer("lodging in Pune?", user_profile=_Profile()))
    assert "Rahul" in captured["system"]
    assert "first message of the conversation" in captured["system"]

    pipe = _pipe(_DOMESTIC, [[AIMessageChunk(content=text)]])
    pipe.llm = _SpyLLM([[AIMessageChunk(content=text)]])
    "".join(pipe.stream_answer("lodging in Pune?"))
    assert "Rahul" not in captured["system"]
    assert "FRIENDLY & PERSONAL" not in captured["system"]


def test_leave_record_injected_only_with_profile_record():
    """Leave scope + a profile carrying DOJ/usage -> the system prompt carries
    the HR record; anonymous caller -> it doesn't (impersonal fallback)."""
    from datetime import date as _date

    captured = {}

    class _SpyLLM(_FakeLLM):
        def stream(self, messages):
            captured["system"] = messages[0].content
            return super().stream(messages)

    leave_route = Route(scopes=("leave",), trip_type=None, assumed=False)
    text = "**You have 4 CL left.** (leave.pdf, p.2)"

    prof = _Profile()
    prof.date_of_joining = _date(2019, 3, 11)
    prof.leave_taken = {"PL": 6.0, "SL": 2.0, "CL": 3.0}
    pipe = _pipe(leave_route, [[AIMessageChunk(content=text)]])
    pipe.llm = _SpyLLM([[AIMessageChunk(content=text)]])
    "".join(pipe.stream_answer("how many CL do I have left?", user_profile=prof))
    assert "EMPLOYEE LEAVE RECORD" in captured["system"]
    assert '"CL": 3.0' in captured["system"]
    assert "2019-03-11" in captured["system"]

    pipe = _pipe(leave_route, [[AIMessageChunk(content=text)]])
    pipe.llm = _SpyLLM([[AIMessageChunk(content=text)]])
    "".join(pipe.stream_answer("how many CL do I have left?"))
    assert "EMPLOYEE LEAVE RECORD" not in captured["system"]


def test_later_turn_prompt_forbids_regreeting():
    captured = {}

    class _SpyLLM(_FakeLLM):
        def stream(self, messages):
            captured["system"] = messages[0].content
            return super().stream(messages)

    text = "**Yes.** (domestic travel.pdf, p.2)"
    pipe = _pipe(_DOMESTIC, [[AIMessageChunk(content=text)]])
    pipe.llm = _SpyLLM([[AIMessageChunk(content=text)]])
    history = [("lodging in Pune?", "**...**")]
    "".join(pipe.stream_answer("and boarding?", history, user_profile=_Profile()))
    assert "already underway" in captured["system"]
    assert "first message of the conversation" not in captured["system"]


def test_plain_answer_streams_in_full():
    text = "**Yes — you can claim lodging in Pune.** (domestic travel.pdf, p.2)"
    rounds = [[AIMessageChunk(content=text[i:i + 7]) for i in range(0, len(text), 7)]]
    pipe = _pipe(_DOMESTIC, rounds)
    assert "".join(pipe.stream_answer("lodging in Pune?")) == text


def test_long_answer_arrives_intact():
    text = "A" * 600
    rounds = [[AIMessageChunk(content=text[i:i + 50]) for i in range(0, len(text), 50)]]
    pipe = _pipe(_DOMESTIC, rounds)
    assert "".join(pipe.stream_answer("q")) == text


def test_tool_round_preamble_is_discarded():
    """Round 1: short prose + a tool call. Round 2: the real answer. The user
    must see only the real answer — not 'Let me calculate…' stitched on top."""
    final = "**Your total is 19,500.** (domestic travel.pdf, p.2)"
    rounds = [
        [AIMessageChunk(content="Let me calculate that for you."), _tool_call_chunk()],
        [AIMessageChunk(content=final)],
    ]
    pipe = _pipe(_DOMESTIC, rounds)
    out = "".join(pipe.stream_answer("total for 3 days in Pune?"))
    assert out == final
    assert "Let me calculate" not in out


def test_full_premature_answer_before_tool_call_is_discarded():
    """Regression: the model sometimes writes a COMPLETE (uncalculated, wrong)
    answer and only then emits the tool call. With the old 200-char hold-back
    that prose went live and the user saw two contradictory answers stitched
    together. The pre-tool answer must be dropped wholesale."""
    premature = "**Your total Boarding Allowance is 1500 Rupees.** " * 10
    final = "**Your total Boarding Allowance is 1125 Rupees.** (domestic travel.pdf, p.2)"
    rounds = [
        [AIMessageChunk(content=premature[i:i + 40])
         for i in range(0, len(premature), 40)] + [_tool_call_chunk()],
        [AIMessageChunk(content=final)],
    ]
    pipe = _pipe(_DOMESTIC, rounds)
    out = "".join(pipe.stream_answer("boarding allowance for 38 hours?"))
    assert out == final
    assert "1500" not in out
