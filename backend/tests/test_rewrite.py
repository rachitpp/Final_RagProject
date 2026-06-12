"""Rewrite gate: which queries trigger the (paid, serial) rewrite LLM call,
and what the rewriter is fed. The gate's job is to catch genuine follow-ups
while letting standalone questions through untouched — every false positive
costs a Vertex round-trip before retrieval starts."""
from types import SimpleNamespace

import pytest

from config.settings import settings
from retrieval import rewrite
from retrieval.rewrite import _format_history, _looks_like_followup, rewrite_query


# ------------------------------------------------------------------- the gate

@pytest.mark.parametrize(
    "query",
    [
        "da?",                                  # short / elliptical
        "what about there?",
        "and for foreign trips?",               # sentence-initial continuer
        "Also for band C with hotel bills?",
        "but what if I self-arrange?",
        "can I claim it for the hotel stay?",   # true pronoun
        "do they need prior approval from HR?",
        "is the same allowed for two days instead?",
    ],
)
def test_followups_are_caught(query):
    assert _looks_like_followup(query) is True


@pytest.mark.parametrize(
    "query",
    [
        # Standalone questions full of the function words the old gate matched.
        "Is there a cap on lodging for Pune hotels?",
        "What's the rule for cities that aren't listed in the table?",
        "Can I combine PL with SL in one continuous stretch?",
        "Which class of rail travel is allowed for those in lower bands?",
        "How much can I claim for boarding in this company's domestic policy?",
    ],
)
def test_standalone_questions_pass_through(query):
    assert _looks_like_followup(query) is False


# ------------------------------------------------------------- rewrite_query

def _llm_must_not_be_called():
    raise AssertionError("rewrite LLM should not be invoked")


def test_no_history_means_no_llm_call(monkeypatch):
    monkeypatch.setattr(rewrite, "_rewrite_llm", _llm_must_not_be_called)
    q = "what about there?"
    assert rewrite_query(q, []) == q


def test_standalone_mid_conversation_means_no_llm_call(monkeypatch):
    monkeypatch.setattr(rewrite, "_rewrite_llm", _llm_must_not_be_called)
    q = "Is there a cap on lodging for Pune hotels?"
    assert rewrite_query(q, [("u", "a")]) == q


def test_genuine_followup_is_rewritten(monkeypatch):
    fake = SimpleNamespace(
        invoke=lambda messages: SimpleNamespace(
            content="What is the lodging allowance in Pune?"
        )
    )
    monkeypatch.setattr(rewrite, "_rewrite_llm", lambda: fake)
    out = rewrite_query("what about lodging?", [("DA in Pune?", "DA is ...")])
    assert out == "What is the lodging allowance in Pune?"


def test_rewrite_failure_degrades_to_original(monkeypatch):
    def _boom():
        return SimpleNamespace(invoke=lambda m: (_ for _ in ()).throw(RuntimeError()))

    monkeypatch.setattr(rewrite, "_rewrite_llm", _boom)
    q = "what about lodging?"
    assert rewrite_query(q, [("u", "a")]) == q


# -------------------------------------------------------------- history shape

def test_history_is_truncated_for_the_rewriter():
    """Only the last N turns are fed, and long answers (which carry whole rate
    tables) are clipped — the rewrite prompt must stay small."""
    long_answer = "x" * 5000
    history = [(f"q{i}", long_answer) for i in range(1, 5)]  # q1..q4
    out = _format_history(history)

    kept = history[-settings.rewrite_history_turns:]
    dropped = history[: -settings.rewrite_history_turns]
    for q, _ in kept:
        assert f"User: {q}" in out
    for q, _ in dropped:
        assert f"User: {q}" not in out
    # Each clipped answer: clip chars + the ellipsis marker, nothing like 5000.
    for line in out.splitlines():
        if line.startswith("Assistant: "):
            assert len(line) <= len("Assistant: ") + settings.rewrite_history_clip_chars + 2
            assert line.endswith("…")
