"""Router: the pure label parser (_parse_route) and route_query's failure
modes (retry once on a transient LLM error, then fail honestly — never guess
a scope for an infrastructure failure). No real LLM is called: _classify_llm
is monkeypatched with a fake."""
from types import SimpleNamespace

import pytest

from retrieval import classify
from retrieval.classify import Route, _parse_route, route_query


# ---------------------------------------------------------------- _parse_route

@pytest.mark.parametrize(
    "raw, scopes, trip_type, assumed",
    [
        ("DOMESTIC", ("domestic",), "domestic", False),
        ("FOREIGN", ("foreign",), "foreign", False),
        ("LEAVE", ("leave",), None, False),
        ("DOMESTIC, LEAVE", ("domestic", "leave"), "domestic", False),
        ("FOREIGN, LEAVE", ("foreign", "leave"), "foreign", False),
        # Ambiguous destination -> Domestic tie-break (doctrine, surfaced as assumed).
        ("AMBIGUOUS", ("domestic",), "domestic", True),
        ("AMBIGUOUS, LEAVE", ("domestic", "leave"), "domestic", True),
        # Labels survive surrounding noise and case.
        ("the answer is: domestic.", ("domestic",), "domestic", False),
        # Unparseable -> conservative travel default, flagged assumed.
        ("BANANA", ("domestic",), "domestic", True),
        ("", ("domestic",), "domestic", True),
    ],
)
def test_parse_route(raw, scopes, trip_type, assumed):
    route = _parse_route(raw)
    assert route.scopes == scopes
    assert route.trip_type == trip_type
    assert route.assumed is assumed
    assert route.error is False


def test_parse_route_none_is_off_topic():
    route = _parse_route("NONE")
    assert route == Route(scopes=(), trip_type=None, assumed=False)


# ----------------------------------------------------------------- route_query

class _FlakyLLM:
    """Fails the first `failures` invoke()s, then returns `payload`."""

    def __init__(self, failures: int, payload: str = "LEAVE"):
        self.failures = failures
        self.payload = payload
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("transient vertex error")
        return SimpleNamespace(content=self.payload)


def test_route_query_retries_transient_failure_once(monkeypatch):
    llm = _FlakyLLM(failures=1, payload="LEAVE")
    monkeypatch.setattr(classify, "_classify_llm", lambda: llm)
    route = route_query("how many sick days do I get?")
    assert llm.calls == 2
    assert route.scopes == ("leave",)
    assert route.error is False


def test_route_query_fails_honestly_not_to_domestic(monkeypatch):
    """Both attempts down -> Route(error=True), NOT a guessed domestic route.
    (The old behaviour sent a leave question to the travel corpus + prompt.)"""
    llm = _FlakyLLM(failures=99)
    monkeypatch.setattr(classify, "_classify_llm", lambda: llm)
    route = route_query("how many sick days do I get?")
    assert llm.calls == 2  # exactly one retry, no infinite loop
    assert route.error is True
    assert route.scopes == ()
    assert route.trip_type is None
    assert route.assumed is False
