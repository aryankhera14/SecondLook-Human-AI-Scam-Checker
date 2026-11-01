"""The clarification ablation: condition B must have no way to ask or to see personal context,
and the default (the app and the main benchmark) must be unchanged."""
import asyncio
import json

import pytest

from eval.ablation_clarification import binom_two_sided, no_answers, run_one
from eval.simulated_user import answer_from_card
from secondlook import agent
from secondlook.agent import CheckSession, _build_tools, _execute, _instructions, run_check
from secondlook.config import DATA
from secondlook.memory import MemoryStore
from secondlook.prompts import SECONDLOOK_INSTRUCTIONS, SECONDLOOK_NO_ASK_INSTRUCTIONS

MSGS = {m["id"]: m for m in json.loads((DATA / "messages.json").read_text())}


class SpyClient:
    """Wraps the offline model and records every request the agent sends."""

    def __init__(self):
        from secondlook.mock_model import FakeGroqClient
        self.inner, self.requests = FakeGroqClient(), []
        from types import SimpleNamespace as NS
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        return self.inner.chat.completions.create(**kwargs)


def tool_names(tools):
    return {t["function"]["name"] for t in tools}


def test_no_clarification_offers_no_ask_user_tool():
    assert "ask_user" in tool_names(_build_tools("secondlook"))
    assert tool_names(_build_tools("secondlook", clarification=False)) == {"recall_context", "search_advisories"}


def test_instructions_differ_only_in_the_asking_step():
    assert _instructions("secondlook") == SECONDLOOK_INSTRUCTIONS
    assert _instructions("secondlook", clarification=False) == SECONDLOOK_NO_ASK_INSTRUCTIONS
    a, b = SECONDLOOK_INSTRUCTIONS, SECONDLOOK_NO_ASK_INSTRUCTIONS
    cut_a, cut_b = a.index("4. Decide whether"), b.index("4. Decide whether")
    assert a[:cut_a] == b[:cut_b]  # steps 1-3 identical
    assert a[a.index("5. IMPORTANT"):] == b[b.index("5. IMPORTANT"):]  # output format, tiers and rules identical
    assert "call ask_user" not in b and "cannot ask" in b


def test_stray_ask_user_call_is_refused_and_raises_no_question():
    ctx = agent.RunCtx(now=agent.dt.datetime(2026, 10, 4), memory=MemoryStore(mode="off"),
                       message_text="x", questions_left=2, allow_ask=False)
    out = _execute("ask_user", {"question": "Did you order this?", "context_key": "expecting_delivery"}, ctx)
    assert "not available" in out and ctx.pending is None


def test_no_clarification_never_sends_ask_user_or_context_card_to_the_model():
    m = MSGS["CD06b"]  # a context-dependent scam where condition A asks
    spy = SpyClient()
    res = asyncio.run(run_check(m, "secondlook", no_answers, MemoryStore(mode="off"),
                                agent.dt.datetime(2026, 10, 4), client=spy, clarification=False))
    assert res["questions"] == []
    for req in spy.requests:
        assert "ask_user" not in tool_names(req.get("tools", []))
        text = json.dumps(req["messages"])
        assert "Answer to your question" not in text and "re-confirmed" not in text
        assert "expecting_delivery\": false" not in text and "context_card" not in text


def test_no_clarification_never_calls_the_simulated_person():
    called = []
    for mid in ("CD01b", "CD06b", "CF01", "L02"):
        m = MSGS[mid]
        asyncio.run(run_check(m, "secondlook", lambda q: called.append(q) or "Yes", MemoryStore(mode="off"),
                              agent.dt.datetime(2026, 10, 4), clarification=False))
    assert called == []


def test_session_has_zero_question_budget_without_clarification():
    s = CheckSession(MSGS["CD06b"], clarification=False)
    assert s.max_questions == 0 and s.ctx.allow_ask is False
    assert CheckSession(MSGS["CD06b"]).max_questions == agent.MAX_QUESTIONS  # default unchanged


def test_condition_a_still_asks_and_gets_card_answers():
    r = asyncio.run(run_one(MSGS["CD06b"], "clarification"))
    assert r["error"] is None and r["n_questions"] >= 1
    assert r["questions"][0]["answer"] == answer_from_card({"context_key": r["questions"][0]["context_key"],
                                                            "options": ["Yes", "No", "Not sure"]}, MSGS["CD06b"]["context"])


def test_condition_b_record_has_no_questions():
    r = asyncio.run(run_one(MSGS["CD06b"], "no_clarification"))
    assert r["error"] is None and r["n_questions"] == 0 and r["questions"] == []


def test_no_answers_fails_loudly():
    with pytest.raises(AssertionError):
        no_answers({"context_key": "expecting_delivery"})


def test_seed_is_sent_only_when_set():
    spy = SpyClient()
    agent.set_seed(None)
    asyncio.run(run_check(MSGS["L02"], "secondlook", lambda q: "Yes", client=spy))
    assert all("seed" not in r for r in spy.requests)
    agent.set_seed(619)
    try:
        asyncio.run(run_check(MSGS["L02"], "secondlook", lambda q: "Yes", client=spy))
        assert any(r.get("seed") == 619 for r in spy.requests)
    finally:
        agent.set_seed(None)


def test_exact_sign_test():
    assert binom_two_sided(0, 0) == 1.0
    assert binom_two_sided(5, 5) == pytest.approx(0.0625)
    assert binom_two_sided(3, 4) == pytest.approx(0.625)


def test_results_with_unusual_characters_are_saved_as_utf8(tmp_path):
    """Regression: on Windows the default file encoding (cp1252) cannot store e.g. a non-breaking hyphen."""
    from eval.ablation_clarification import load, save, wtext
    rows = [{"id": "X", "summary": "cash‑on‑delivery “parcel” – ok", "error": None}]
    save(tmp_path, rows)
    assert (tmp_path / "results.jsonl").read_bytes().decode("utf-8")  # valid UTF-8
    assert load(tmp_path) == rows
    wtext(tmp_path / "r.md", "‑")
    assert (tmp_path / "r.md").read_text(encoding="utf-8") == "‑"
