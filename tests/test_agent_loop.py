"""Drives the real Groq agent loop with the offline fake Groq client."""
import asyncio
import datetime as dt
import json

import pytest

from eval.simulated_user import answer_from_card
from secondlook.agent import CheckSession, parse_json, run_check
from secondlook.config import DATA
from secondlook.memory import MemoryStore
from secondlook.mock_model import FakeGroqClient

MSGS = {m["id"]: m for m in json.loads((DATA / "messages.json").read_text())}


def check(mid, condition="secondlook", memory=None, now=None, client=None):
    m = MSGS[mid]
    return asyncio.run(run_check(m, condition, lambda q: answer_from_card(q, m["context"]), memory, now, client=client))


def test_pauses_for_question_then_resumes():
    async def go():
        s = CheckSession(MSGS["CD06b"])
        step = await s.start()
        assert step["type"] == "question" and step["context_key"] == "expecting_delivery"
        return await s.answer("No")
    step = asyncio.run(go())
    assert step["type"] == "final" and step["result"]["verdict"]["tier"] == "likely_scam"


def test_question_limit_enforced_by_harness():
    async def go():
        return await CheckSession(MSGS["CD06b"], max_questions=0).start()
    step = asyncio.run(go())
    assert step["type"] == "final" and step["result"]["questions"] == []


def test_context_fits_scam_never_looks_fine():
    for mid in [k for k, m in MSGS.items() if m["category"] == "context_fits_scam"]:
        assert check(mid)["verdict"]["tier"] != "looks_fine", mid


def test_baselines_return_real_verdicts_not_cant_tell():
    assert check("S01", "message_only")["verdict"]["tier"] == "likely_scam"
    assert check("L02", "message_only")["verdict"]["tier"] == "looks_fine"
    assert check("CD06b", "ask_prompted")["verdict"]["tier"] == "likely_scam"


def test_message_only_baseline_never_asks():
    assert check("CD01b", "message_only")["questions"] == []


def test_fenced_json_is_accepted():
    assert check("CF01", client=FakeGroqClient(fenced=True))["verdict"]["tier"] == "likely_scam"


def test_broken_json_is_an_error_not_a_silent_verdict():
    with pytest.raises(RuntimeError):
        check("L02", client=FakeGroqClient(broken_json=True))


def test_parse_json_variants():
    assert parse_json('```json\n{"tier": "x"}\n```') == {"tier": "x"}
    assert parse_json('Verdict: {"tier": "x"} done') == {"tier": "x"}
    assert parse_json("no json here") is None


def test_memory_answers_question_next_time():
    mem = MemoryStore(mode="adaptive")
    now = dt.datetime(2026, 10, 5)
    r1 = check("CD06a", memory=mem, now=now)
    for s in r1["verdict"]["memory_suggestions"]:
        mem.add(s, now)
    r2 = check("CD06a", memory=mem, now=now + dt.timedelta(days=1))
    assert len(r1["questions"]) == 1 and len(r2["questions"]) == 0 and r2["recalled"]


def test_out_of_scope_is_flagged():
    assert check("S02")["out_of_scope"] is True
    assert check("S01")["out_of_scope"] is False
