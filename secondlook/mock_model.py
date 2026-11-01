"""Rule-based stand-in for the Groq model, used ONLY for offline tests and demos.

FakeGroqClient answers `client.chat.completions.create(...)` in the same shape as
the Groq SDK, so mock runs go through the real agent loop, tools, pausing,
memory rules and guardrails. Its verdicts come from keyword rules and are NOT
research results.
"""
import itertools
import json
import re
from types import SimpleNamespace as NS

from .advisories import load_advisories
from .guardrails import URL_RE, _asks_for_code
from .schemas import CONTEXT_QUESTIONS

_ids = itertools.count(1)
OFFICIAL_DOMAINS = {"singpost.com", "nlb.gov.sg", "shopee.sg", "dbs.com.sg", "gov.sg"}
TYPE_RULES = [
    ("job", r"\b(job|recruit\w*|application|applying|interview|intern)\b"),
    ("government", r"\b(ministry|iras|police|nric|officer from)\b"),
    ("investment", r"\b(stock|returns|invest\w*)\b"),
    ("delivery", r"\b(parcel|delivery|deliver\w*|courier|cod|singpost|ninja van|customs)\b"),
    ("ecommerce", r"\b(carousell|shopee|buy your|refund)\b"),
    ("otp_banking", r"\b(otp|bank|dbs|ocbc|transfer\w*|card|singpass|code)\b"),
    ("personal", r"\b(new number|dinner|home|it's)\b"),
]
CONTEXT_CUES = [
    ("expecting_delivery", r"\bcod\b|cash on delivery|prepare (exact )?cash"),
    ("requested_otp_or_login", r"\botp\b|\bcode\b|logged in|log in"),
    ("applied_for_job", r"application|applying|interview|recruit"),
    ("initiated_payment_or_refund", r"\btransferred\b|\brefund\b"),
    ("knows_sender_personally", r"new number"),
]
LASTING_KEYS = {"expecting_delivery": "I am expecting a parcel delivery",
                "applied_for_job": "I am applying for jobs",
                "made_listing_selling_item": "I am selling an item online"}


def _line(adv_id: str, startswith: str) -> tuple[str, str]:
    for line in load_advisories()[adv_id].lines:
        if line.lower().startswith(startswith.lower()):
            return adv_id, line
    raise KeyError(startswith)


def red_flags(text: str) -> list[dict]:
    flags = []

    def add(phrase, reason, adv, start):
        a, q = _line(adv, start)
        flags.append({"phrase": phrase, "reason": reason, "advisory_id": a, "advisory_quote": q})
    for m in URL_RE.finditer(text):
        host = m.group(0).lower().split("/")[0].removeprefix("https://").removeprefix("http://")
        if not any(host == d or host.endswith("." + d) for d in OFFICIAL_DOMAINS):
            add(m.group(0), "The link does not match the organisation's official website.", "spot_scam_sms", "Fraudulent Links")
    for pat, adv, start, reason in [
        (r"immediately|within \d+ ?h\w*|very urgent|avoid suspension|suspended today", "spot_scam_sms", "Urgent Language", "Pressure to act fast."),
        (r"deposit|pay[^.]{0,20}to start", "job_scams", "It is likely a scam if the job requires you to: Pay upfront", "A job that needs payment up front."),
        (r"safe account", "government_impersonation", "Victims would then be instructed", "Officials never ask you to move money to a 'safe account'."),
        (r"customs fee|delivery fee", "ecommerce_scams", "Asks you to pay additional customs", "Unexpected fee before delivery."),
        (r"carousell protection", "ecommerce_scams", "Needs you to click on links", "Payment claims that need you to click a link."),
        (r"money laundering", "government_impersonation", "The scammers would accuse", "Accusation of a crime to scare you."),
        (r"guaranteed \d+%", "spot_scam_sms", "Unsolicited Attachments or Payment Requests", "Guaranteed returns are a classic investment-scam promise."),
        (r"won an? |you won|prize", "spot_scam_sms", "Unsolicited Attachments or Payment Requests", "Unexpected prize."),
    ]:
        m = re.search(pat, text, re.I)
        if m:
            add(m.group(0), reason, adv, start)
    if _asks_for_code(text):
        m = re.search(r"\b(otp|code|password|pin)\b", text, re.I)
        add(m.group(0), "Nobody legitimate needs you to share a one-time code.", "phishing_scams", "Requests for your One-Time passwords")
    return flags


def guess_type(text: str) -> str:
    for t, pat in TYPE_RULES:
        if re.search(pat, text, re.I):
            return t
    return "other"


class _Completions:
    def __init__(self, owner):
        self.owner = owner

    def create(self, model, messages, temperature=None, tools=None, tool_choice=None, **_):
        self.owner.calls += 1
        return self.owner._respond(messages, tools or [])


class FakeGroqClient:
    """Offline stand-in with the Groq client's shape: client.chat.completions.create(...)."""

    def __init__(self, fenced: bool = False, broken_json: bool = False):
        self.fenced, self.broken_json, self.calls = fenced, broken_json, 0
        self.chat = NS(completions=_Completions(self))

    # ---- response helpers ----
    def _calls(self, calls):
        tcs = [NS(id=f"call_{next(_ids)}", type="function",
                  function=NS(name=name, arguments=json.dumps(args))) for name, args in calls]
        return NS(choices=[NS(message=NS(content="", tool_calls=tcs), finish_reason="tool_calls")],
                  usage=NS(total_tokens=440))

    def _final(self, payload):
        text = json.dumps(payload)
        if self.broken_json:
            text = "Here is my verdict: it is probably fine."
        elif self.fenced:
            text = f"```json\n{text}\n```"
        return NS(choices=[NS(message=NS(content=text, tool_calls=None), finish_reason="stop")],
                  usage=NS(total_tokens=750))

    # ---- rule-based behaviour ----
    def _respond(self, messages, tools):
        system = messages[0]["content"]
        text = re.search(r"<<<\n(.*)\n>>>", messages[1]["content"], re.S).group(1)
        tool_names = {t["function"]["name"] for t in tools}
        names_by_id, outputs, asked, known = {}, {}, set(), {}
        for m in messages[1:]:
            for tc in m.get("tool_calls") or []:
                names_by_id[tc["id"]] = tc["function"]["name"]
                if tc["function"]["name"] == "ask_user":
                    asked.add(json.loads(tc["function"]["arguments"]).get("context_key"))
            if m.get("role") == "tool":
                outputs[names_by_id.get(m["tool_call_id"])] = m["content"]
            if m.get("role") == "user":
                a = re.search(r"\((\w+)\): (Yes|No|Not sure)", m["content"])
                if a:
                    known[a.group(1)] = {"Yes": True, "No": False}.get(a.group(2))
        recalled = {}
        if outputs.get("recall_context", "").startswith("["):
            recalled = {f["context_key"]: f["value"] for f in json.loads(outputs["recall_context"])}
        binary = '"is_scam"' in system
        mtype = guess_type(text)

        if not binary and "recall_context" not in names_by_id.values():
            return self._calls([("recall_context", {"message_type": mtype}),
                                ("search_advisories", {"query": text[:120], "message_type": mtype})])
        flags = red_flags(text)
        key = next((k for k, pat in CONTEXT_CUES if re.search(pat, text, re.I)), None)
        value = known.get(key, recalled.get(key)) if key else None
        limit_hit = "QUESTION_LIMIT_REACHED" in outputs.get("ask_user", "")
        if not flags and "ask_user" in tool_names and key and value is None and key not in asked and not limit_hit:
            return self._calls([("ask_user", {"question": CONTEXT_QUESTIONS[key], "context_key": key,
                                              "options": ["Yes", "No", "Not sure"]})])
        if binary:
            return self._final({"is_scam": bool(flags) or value is False, "reason": "Rule-based mock verdict."})
        if flags:
            tier, summary = "likely_scam", "This message shows warning signs listed in official scam advisories."
        elif key and value is False:
            tier, summary = "likely_scam", "Your answer does not match what this message assumes, so it is likely a scam or someone else's activity."
        elif key and value is None:
            tier, summary = "cant_tell", "Whether this is genuine depends on details we could not confirm."
        else:
            tier, summary = "looks_fine", "No warning signs found, and it matches what you told us."
        used = ([f"You answered {key} = {value}"] if key in known else
                [f"Remembered: {key} = {value}"] if key in recalled else [])
        suggestions = []
        if key in LASTING_KEYS and known.get(key) is True:
            suggestions.append({"fact": LASTING_KEYS[key], "context_key": key, "value": True, "applies_to": [mtype]})
        return self._final({"message_type": mtype, "risky_requests": [], "tier": tier, "summary": summary,
                            "red_flags": flags, "safe_next_step": "", "context_used": used,
                            "memory_suggestions": suggestions})
