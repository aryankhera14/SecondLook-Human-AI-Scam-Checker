"""The SecondLook agent loop (Groq, OpenAI-compatible tool calling) and the evaluation baselines.

A check runs as a session that can pause for the person: when the model calls
ask_user - or when the app needs to re-check an old remembered fact - the loop
stops, the app shows the question, and the next run continues the same history
with the answer. The harness, not the model, enforces the question limit and all
memory rules (see memory.py).
"""
import asyncio
import datetime as dt
import json
import re
from dataclasses import asdict, dataclass, field
from typing import get_args

from . import advisories
from .config import (MAX_QUESTIONS, MODEL, PROVIDER, REASONING_EFFORT, TEMPERATURE, groq_key,
                     openrouter_key, use_mock)
from .guardrails import apply_policy, check_red_flags, detect_risky_requests
from .memory import MemoryStore
from .prompts import (ASK_PROMPTED_INSTRUCTIONS, MESSAGE_ONLY_INSTRUCTIONS,
                      SECONDLOOK_INSTRUCTIONS, SECONDLOOK_NO_ASK_INSTRUCTIONS, format_message)
from .schemas import (FOCUS_MESSAGE_TYPES, RECHECK_QUESTIONS, ContextKey, MessageType,
                      normalise_verdict)

CONDITIONS = ("message_only", "ask_prompted", "secondlook")
FAKE_FINAL_TOOLS = {"json", "final", "final_answer", "verdict", "answer", "response", "output", "result"}
_SETTINGS = {"send_reasoning_effort": MODEL.startswith("openai/gpt-oss") and bool(REASONING_EFFORT),
             "seed": None, "seed_supported": None}  # seed is only set by evaluation scripts (best effort)


def set_seed(seed: int | None):
    """Ask the provider for best-effort repeatable sampling. Not a guarantee of determinism."""
    _SETTINGS["seed"], _SETTINGS["seed_supported"] = seed, None


class QuotaExhausted(RuntimeError):
    """The provider's daily token limit is used up; the run should stop and be resumed later."""


def _error_info(e) -> tuple:
    status = getattr(e, "status_code", None)
    body = getattr(e, "body", None)
    err = body.get("error", body) if isinstance(body, dict) else {}
    return status, (err if isinstance(err, dict) else {})


def _retry_after(msg: str) -> float:
    m = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", msg)
    return int(m.group(1) or 0) * 60 + float(m.group(2)) if m else 5.0


async def _create(client, kwargs: dict, retries: int = 8):
    """One model call, waiting out per-minute rate limits; stops cleanly at the daily limit."""
    for attempt in range(retries + 1):
        try:
            return await asyncio.to_thread(client.chat.completions.create, **kwargs)
        except Exception as e:
            status, err = _error_info(e)
            msg = str(err.get("message") or e)
            if status == 429:
                if "per day" in msg:
                    raise QuotaExhausted(msg) from e
                if attempt < retries:
                    await asyncio.sleep(min(_retry_after(msg) + 1 + attempt * 2, 90))
                    continue
            if status == 400 and "reasoning_effort" in kwargs and "reasoning" in msg.lower():
                kwargs.pop("reasoning_effort")  # this model does not accept the setting
                _SETTINGS["send_reasoning_effort"] = False
                continue
            if status == 400 and "seed" in kwargs and "seed" in msg.lower():
                kwargs.pop("seed")  # the provider does not accept a seed
                _SETTINGS["seed"], _SETTINGS["seed_supported"] = None, False
                continue
            raise
MAX_STEPS = 12
OPTIONS = ["Yes", "No", "Not sure"]


@dataclass
class RunCtx:
    now: dt.datetime
    memory: MemoryStore
    message_text: str = ""
    pending: dict | None = None
    questions_left: int = 0
    allow_ask: bool = True  # False only in the clarification ablation
    rechecked: set = field(default_factory=set)
    recalled: list = field(default_factory=list)
    searches: list = field(default_factory=list)


def answer_to_bool(answer: str | None) -> bool | None:
    a = (answer or "").strip().lower()
    return True if a.startswith("yes") else False if a.startswith("no") else None


# ---------------- tools (executed by the application) ----------------
def search_advisories(ctx: RunCtx, query: str, message_type: str) -> str:
    ctx.searches.append(query)
    hits = advisories.search(query, message_type)  # id + exact line only: keeps tokens down
    return json.dumps([{"advisory_id": h["advisory_id"], "quote": h["quote"]} for h in hits], ensure_ascii=False)


def recall_context(ctx: RunCtx, message_type: str) -> str:
    """Return remembered context for this message type. Old facts that would relax caution on a
    risky message are NOT handed over silently: the app pauses to re-check them with the person."""
    risky = bool(detect_risky_requests(ctx.message_text))
    usable = []
    for item in ctx.memory.active(ctx.now, message_type):
        if ctx.memory.needs_recheck(item, ctx.now, risky) and item.id not in ctx.rechecked:
            if ctx.questions_left > 0 and not ctx.pending:
                ctx.rechecked.add(item.id)
                ctx.pending = {"question": RECHECK_QUESTIONS[item.context_key], "context_key": item.context_key,
                               "options": OPTIONS, "kind": "recheck", "memory_id": item.id, "fact": item.fact}
                return (f"PAUSED: the app is asking the person to re-confirm remembered context "
                        f"\"{item.fact}\" ({item.context_key}) before it is used.")
            continue  # cannot re-check (no questions left): do not rely on the old fact
        usable.append(item)
    ctx.recalled = [asdict(i) for i in usable]
    if not usable:
        return "No remembered context for this message type."
    return json.dumps([{"fact": i.fact, "context_key": i.context_key, "value": i.value} for i in usable])


def ask_user(ctx: RunCtx, question: str, context_key: str, options: list[str] | None) -> str:
    if ctx.pending:
        return "Only one question at a time. Wait for the answer."
    if ctx.questions_left <= 0:  # limit enforced by the application, not the prompt
        return "QUESTION_LIMIT_REACHED: do not ask again. Give your verdict now with what you know."
    ctx.pending = {"question": question, "context_key": context_key,
                   "options": options or OPTIONS, "kind": "model"}
    return "WAITING_FOR_USER"


def _execute(name: str, args: dict, ctx: RunCtx) -> str:
    try:
        if name == "search_advisories":
            return search_advisories(ctx, str(args.get("query", "")), args.get("message_type", "other"))
        if name == "recall_context":
            return recall_context(ctx, args.get("message_type", "other"))
        if name == "ask_user":
            if not ctx.allow_ask:  # ablation: the tool does not exist, so no question can reach a person
                return "Unknown tool: ask_user. Asking the person is not available; give your verdict now."
            return ask_user(ctx, str(args.get("question", "")), args.get("context_key", ""), args.get("options"))
    except Exception as e:  # a tool error is reported to the model, not raised
        return f"TOOL_ERROR: {type(e).__name__}: {e}"
    return f"Unknown tool: {name}"


def _fn(name, description, properties, required):
    return {"type": "function", "function": {"name": name, "description": description, "parameters": {
        "type": "object", "properties": properties, "required": required}}}


MESSAGE_TYPE_PARAM = {"type": "string", "enum": list(get_args(MessageType))}
ASK_USER_TOOL = _fn("ask_user", "Ask the person ONE yes/no question about their own situation, only when the answer changes the verdict.",
                    {"question": {"type": "string"},
                     "context_key": {"type": "string", "enum": list(get_args(ContextKey))},
                     "options": {"type": "array", "items": {"type": "string"}}},
                    ["question", "context_key", "options"])
RECALL_TOOL = _fn("recall_context", "Return context the person approved for remembering that applies to this message type.",
                  {"message_type": MESSAGE_TYPE_PARAM}, ["message_type"])
SEARCH_TOOL = _fn("search_advisories", "Search official scam advisories. Returns exact lines you may quote, with advisory_id.",
                  {"query": {"type": "string"}, "message_type": MESSAGE_TYPE_PARAM}, ["query", "message_type"])


def _build_tools(condition: str, clarification: bool = True) -> list[dict]:
    if condition == "secondlook":
        return [RECALL_TOOL, SEARCH_TOOL] + ([ASK_USER_TOOL] if clarification else [])
    if condition == "ask_prompted":
        return [ASK_USER_TOOL]
    return []


def _instructions(condition: str, clarification: bool = True) -> str:
    if condition == "secondlook" and not clarification:
        return SECONDLOOK_NO_ASK_INSTRUCTIONS
    return {"secondlook": SECONDLOOK_INSTRUCTIONS, "ask_prompted": ASK_PROMPTED_INSTRUCTIONS,
            "message_only": MESSAGE_ONLY_INSTRUCTIONS}[condition]


def parse_json(content: str) -> dict | None:
    """Accept plain JSON or JSON wrapped in ```json fences or surrounding text."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (content or "").strip())
    for candidate in (text, text[text.find("{"): text.rfind("}") + 1] if "{" in text else ""):
        try:
            value = json.loads(candidate)
            if isinstance(value, dict):
                return value
        except (json.JSONDecodeError, ValueError):
            pass
    return None


async def _run_agent_loop(client, condition: str, history: list[dict], ctx: RunCtx) -> dict:
    """Call the model, execute its tool calls, and stop on a final JSON answer or a pending question."""
    messages = [{"role": "system", "content": _instructions(condition, ctx.allow_ask)}] + history
    tools = _build_tools(condition, ctx.allow_ask)
    tokens, repaired, tool_fixes = 0, False, 0
    tool_names = ", ".join(t["function"]["name"] for t in tools) or "none"
    for _ in range(MAX_STEPS):
        kwargs = {"model": MODEL, "messages": messages, "temperature": TEMPERATURE}
        if tools:
            kwargs.update(tools=tools, tool_choice="auto")
        if _SETTINGS["send_reasoning_effort"]:
            kwargs["reasoning_effort"] = REASONING_EFFORT
        if _SETTINGS["seed"] is not None:
            kwargs["seed"] = _SETTINGS["seed"]
        try:
            resp = await _create(client, kwargs)
        except QuotaExhausted:
            raise
        except Exception as e:
            status, err = _error_info(e)
            if status != 400 or err.get("code") != "tool_use_failed" or tool_fixes >= 2:
                raise
            # gpt-oss on Groq sometimes sends its final answer as a call to a non-existent tool
            # (e.g. "json"), misspells a tool, or emits broken arguments. Recover or ask again.
            gen = parse_json(str(err.get("failed_generation") or ""))
            args = gen.get("arguments") if gen else None
            if isinstance(args, str):
                args = parse_json(args)
            if gen and str(gen.get("name", "")).lower() in FAKE_FINAL_TOOLS and isinstance(args, dict):
                messages.append({"role": "assistant", "content": json.dumps(args)})
                return {"result": args, "history": messages[1:], "tokens": tokens, "recovered": True}
            tool_fixes += 1
            messages.append({"role": "user", "content":
                             f"Your last reply was rejected: it called a tool that does not exist or gave invalid "
                             f"tool arguments. The only tools are: {tool_names}. When you are ready to answer, do NOT "
                             f"call a tool - reply with the JSON object as plain text."})
            continue
        tokens += getattr(resp.usage, "total_tokens", 0) or 0
        msg = resp.choices[0].message
        calls = getattr(msg, "tool_calls", None) or []
        if calls:
            messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
                {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}}
                for c in calls]})
            for c in calls:
                try:
                    args = json.loads(c.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                messages.append({"role": "tool", "tool_call_id": c.id, "content": _execute(c.function.name, args, ctx)})
            if ctx.pending:
                return {"pending": ctx.pending, "history": messages[1:], "tokens": tokens}
            continue
        content = msg.content or ""
        messages.append({"role": "assistant", "content": content})
        parsed = parse_json(content)
        if parsed is not None:
            return {"result": parsed, "history": messages[1:], "tokens": tokens}
        if repaired:
            return {"error": f"Model did not return valid JSON: {content[:200]!r}", "history": messages[1:], "tokens": tokens}
        repaired = True
        messages.append({"role": "user", "content": "Your last reply was not valid JSON. Reply again with ONLY the JSON object."})
    return {"error": "Too many steps without a final answer.", "history": messages[1:], "tokens": tokens}


def make_client():
    if use_mock():
        from .mock_model import FakeGroqClient
        return FakeGroqClient()
    if PROVIDER == "openrouter":
        from openai import OpenAI
        return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=openrouter_key())
    from groq import Groq
    return Groq(api_key=groq_key())


class CheckSession:
    """One message check. Call start(), then answer() while a question is pending."""

    def __init__(self, message: dict, condition: str = "secondlook", memory: MemoryStore | None = None,
                 now: dt.datetime | None = None, max_questions: int = MAX_QUESTIONS, client=None,
                 clarification: bool = True):
        assert condition in CONDITIONS
        self.message, self.condition = message, condition
        self.clarification = clarification
        self.now = now or dt.datetime.now()
        self.memory = memory or MemoryStore(mode="off")
        self.ctx = RunCtx(now=self.now, memory=self.memory, message_text=message["text"], allow_ask=clarification)
        self.max_questions = 0 if condition == "message_only" or not clarification else max_questions
        self.client = client or make_client()
        self.history: list[dict] = [{"role": "user", "content": format_message(message, self.now)}]
        self.questions: list[dict] = []
        self.memory_events: list[str] = []
        self.tokens = 0
        self.recovered = False
        self.result: dict | None = None

    async def _run(self):
        self.ctx.pending = None
        self.ctx.questions_left = self.max_questions - len(self.questions)
        res = await _run_agent_loop(self.client, self.condition, self.history, self.ctx)
        self.tokens += res.get("tokens", 0)
        self.history = res["history"]
        self.recovered = self.recovered or bool(res.get("recovered"))
        if res.get("pending"):
            q = dict(res["pending"])
            self.questions.append(q)
            return {"type": "question", **q}
        if res.get("error"):
            return {"type": "error", "error": res["error"]}
        try:
            self.result = self._finalise(res["result"])
        except ValueError as e:
            return {"type": "error", "error": str(e)}
        return {"type": "final", "result": self.result}

    async def start(self):
        return await self._run()

    async def answer(self, answer: str):
        q = self.questions[-1]
        q["answer"] = answer
        value = answer_to_bool(answer)
        if q.get("kind") == "recheck":  # layer 3: the app's own re-check of an old fact
            if value is True:
                self.memory.confirm(q["memory_id"], self.now)
                self.memory_events.append(f"Re-confirmed and renewed: “{q['fact']}”")
            elif value is False:
                self.memory.delete(q["memory_id"])
                self.memory_events.append(f"Forgotten because you said it is no longer true: “{q['fact']}”")
            text = f"The person re-confirmed remembered context ({q['context_key']}): {answer}"
        else:  # layer 4: an answer that contradicts memory replaces it
            event = self.memory.apply_answer(q["context_key"], value, self.now)
            if event:
                self.memory_events.append(f"Memory for {q['context_key']} {event} by your answer.")
            text = f"Answer to your question \"{q['question']}\" ({q['context_key']}): {answer}"
        self.history.append({"role": "user", "content": text})
        return await self._run()

    def _finalise(self, out: dict) -> dict:
        text = self.message["text"]
        base = {"condition": self.condition, "questions": self.questions, "tokens": self.tokens,
                "recovered": self.recovered,
                "memory_events": self.memory_events, "forget_offers": [], "adjustments": [],
                "red_flags": [], "recalled": []}
        if self.condition != "secondlook":
            if "is_scam" not in out:
                raise ValueError(f"baseline answer has no is_scam field: {str(out)[:150]}")
            is_scam = out["is_scam"] if isinstance(out["is_scam"], bool) else str(out["is_scam"]).lower() == "true"
            tier = "likely_scam" if is_scam else "looks_fine"
            verdict = {"message_type": "other", "risky_requests": [], "tier": tier, "summary": str(out.get("reason", "")),
                       "red_flags": [], "safe_next_step": "", "context_used": [], "memory_suggestions": []}
            return {**base, "verdict": verdict, "raw_tier": tier, "out_of_scope": False}
        raw = normalise_verdict(out)
        final, notes = apply_policy(raw, text)
        return {**base, "verdict": final, "raw_tier": raw["tier"], "adjustments": notes,
                "red_flags": check_red_flags(final["red_flags"], text), "recalled": self.ctx.recalled,
                "forget_offers": self.memory.completion_offers(text, final["tier"], self.now),
                "out_of_scope": final["message_type"] not in FOCUS_MESSAGE_TYPES}


async def run_check(message: dict, condition: str, answer_fn, memory: MemoryStore | None = None,
                    now: dt.datetime | None = None, forget_fn=None, client=None,
                    clarification: bool = True) -> dict:
    """Run a whole check, answering questions with answer_fn(question) -> str.
    forget_fn(offer) -> bool decides on event-based 'forget this?' offers (default: keep).
    clarification=False is the Idea 1 ablation: no ask_user tool, no question limit left, no answers."""
    s = CheckSession(message, condition, memory, now, client=client, clarification=clarification)
    step = await s.start()
    while step["type"] == "question":
        if not clarification:  # cannot happen (max_questions is 0); refuse rather than leak an answer
            raise RuntimeError("A question was raised although clarification is disabled.")
        step = await s.answer(answer_fn(step))
    if step["type"] == "error":
        raise RuntimeError(step["error"])
    result = step["result"]
    for offer in result["forget_offers"]:
        if forget_fn and forget_fn(offer):
            s.memory.delete(offer["item_id"])
            result["memory_events"].append(f"Forgotten after the situation ended: “{offer['fact']}”")
    return result
