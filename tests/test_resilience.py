"""Failure modes seen in the first live Groq runs (31 Oct): the model sending its final answer as a
fake 'json' tool call, misspelled tools, per-minute and per-day rate limits."""
import asyncio
import json
import os
import pathlib
import subprocess
import sys

import pytest

from secondlook import agent
from secondlook.agent import QuotaExhausted, run_check
from secondlook.mock_model import FakeGroqClient

MSG = {"id": "t", "channel": "SMS", "sender": "", "text": "Dinner at 7 at the usual place? Bring the board game!"}
ROOT = pathlib.Path(__file__).resolve().parent.parent


class ApiError(Exception):
    def __init__(self, status, body):
        super().__init__(str(body))
        self.status_code, self.body = status, body


def tool_failed(name, arguments):
    gen = json.dumps({"name": name, "arguments": arguments})
    return ApiError(400, {"error": {"code": "tool_use_failed", "message": "Tool call validation failed",
                                    "failed_generation": gen}})


class Flaky(FakeGroqClient):
    """Raises the given errors on the first calls, then behaves like the normal fake client."""
    def __init__(self, errors):
        super().__init__()
        self.errors = list(errors)
        inner = self.chat.completions.create
        def create(**kw):
            if self.errors:
                raise self.errors.pop(0)
            return inner(**kw)
        self.chat.completions.create = create


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    async def fast(_):
        return None
    monkeypatch.setattr(agent.asyncio, "sleep", fast)


def run(client, condition="secondlook"):
    return asyncio.run(run_check(MSG, condition, lambda q: "Yes", client=client))


def test_final_answer_sent_as_fake_json_tool_is_recovered():
    verdict = {"message_type": "personal", "risky_requests": [], "tier": "looks_fine", "summary": "ok",
               "red_flags": [], "safe_next_step": "", "context_used": [], "memory_suggestions": []}
    res = run(Flaky([tool_failed("json", verdict)]))
    assert res["verdict"]["tier"] == "looks_fine" and res["recovered"] is True


def test_baseline_fake_json_tool_is_recovered():
    res = run(Flaky([tool_failed("JSON", {"is_scam": True, "reason": "x"})]), "ask_prompted")
    assert res["verdict"]["tier"] == "likely_scam"


def test_misspelled_tool_gets_a_correction_and_retry():
    client = Flaky([tool_failed("search_advisals", {"query": "x"})])
    assert run(client)["verdict"]["tier"] == "looks_fine"


def test_per_minute_rate_limit_is_waited_out():
    err = ApiError(429, {"error": {"message": "Rate limit ... tokens per minute (TPM) ... Please try again in 1.5s."}})
    assert run(Flaky([err, err]))["verdict"]["tier"] == "looks_fine"


def test_daily_limit_stops_the_run():
    err = ApiError(429, {"error": {"message": "Rate limit ... tokens per day (TPD) ... try again in 7m38.7s."}})
    with pytest.raises(QuotaExhausted):
        run(Flaky([err]))


def test_unrelated_errors_are_not_swallowed():
    with pytest.raises(ApiError):
        run(Flaky([ApiError(401, {"error": {"message": "Invalid API key"}})]))


def test_resume_reruns_only_failed_checks(tmp_path):
    env = {**os.environ, "SECONDLOOK_MOCK": "1", "PYTHONPATH": str(ROOT)}
    cmd = [sys.executable, "-m", "eval.run_eval", "--limit", "3"]
    out = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, check=True).stdout
    folder = pathlib.Path(out.strip().split("Saved to ")[-1].splitlines()[0])
    rows = [json.loads(l) for l in (folder / "records.jsonl").read_text().splitlines()]
    rows[0] = {k: rows[0][k] for k in ("id", "condition", "rep", "label", "category", "topic")} | {"error": "fake"}
    (folder / "records.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    out = subprocess.run(cmd + ["--resume", str(folder)], cwd=ROOT, env=env, capture_output=True, text=True, check=True).stdout
    assert "Running 1 checks" in out and "keeping 8" in out
    rows = [json.loads(l) for l in (folder / "records.jsonl").read_text().splitlines()]
    assert len(rows) == 9 and not any(r.get("error") for r in rows)


def test_app_shows_friendly_error_on_rate_limit(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    import secondlook.mock_model as mm
    monkeypatch.setattr("secondlook.config.RUNTIME", tmp_path)
    err = ApiError(429, {"error": {"message": "Rate limit ... tokens per day (TPD) ... try again in 7m1s."}})
    def boom(self, messages, tools):
        raise err
    monkeypatch.setattr(mm.FakeGroqClient, "_respond", boom)
    at = AppTest.from_file("../app.py", default_timeout=60).run()
    at.text_area[0].input("Ninja Van: Your COD parcel (SGD 48.90) will arrive today.").run()
    at.button[0].click().run()
    assert not at.exception
    assert any("daily token limit" in e.value for e in at.error)


def test_openrouter_provider_builds_openai_client(monkeypatch):
    pytest.importorskip("openai", reason="optional OpenRouter provider; only needed if you use OpenRouter")
    import importlib
    from secondlook import config
    monkeypatch.setenv("SECONDLOOK_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("SECONDLOOK_MOCK", "0")
    importlib.reload(config)
    importlib.reload(agent)
    try:
        assert not config.use_mock()
        client = agent.make_client()
        assert "openrouter.ai" in str(client.base_url)
    finally:
        monkeypatch.setenv("SECONDLOOK_PROVIDER", "groq")
        monkeypatch.setenv("SECONDLOOK_MOCK", "1")
        importlib.reload(config)
        importlib.reload(agent)
