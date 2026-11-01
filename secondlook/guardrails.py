"""Rules enforced in code after the model answers (Week 4: instructions guide,
the application enforces). The model cannot talk its way past these.

1. Risky requests are detected from the message text itself, not only from the model.
2. "Looks fine" is only allowed when the message asks for nothing risky.
3. The safe next step never routes the user through the message's own link or number.
4. Red-flag phrases and advisory quotes are checked verbatim; unverified ones are marked.
"""
import re

from .advisories import load_advisories, quote_exists

URL_RE = re.compile(r"\b(?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s]*)?", re.I)
PHONE_RE = re.compile(r"(?:\+\d{1,3}[\s-]?)?\b(?:1800[\s-]?\d{3}[\s-]?\d{4}|[3689]\d{3}[\s-]?\d{4})\b")
MONEY_RE = re.compile(r"(?:S?\$|SGD)\s?\d", re.I)
PAY_RE = re.compile(r"\b(pay|payment fee|fee|deposit|transfer|prepare (?:exact )?cash|cash on delivery|cod)\b", re.I)
CODE_WORD = r"(otp|code|password|pin)"
CODE_VERB = r"(forward|send|share|give|tell|provide)"
CODE_ASK_RES = [re.compile(r"\b" + CODE_VERB + r"\b[^.!?]{0,30}\b" + CODE_WORD + r"\b", re.I),
                re.compile(r"\b" + CODE_WORD + r"\b.{0,80}?\b" + CODE_VERB + r"\s+(it|them|the|this|that)\b", re.I | re.S)]
NEGATION_BEFORE = re.compile(r"(never|not|n't|do not)\s+(?:\w+\s+){0,2}$", re.I)
REPLY_RE = re.compile(r"\breply\b", re.I)
INSTALL_RE = re.compile(r"\b(download|install)\b[^.]{0,40}\b(app|apk)\b", re.I)
SAFE_ACCOUNT_RE = re.compile(r"\b(safe account|transfer your savings|transfer to)\b", re.I)

DEFAULT_STEPS = {
    "delivery": "Check the delivery status in the courier's or shop's official app, or type their official website yourself. Do not use the link or number in this message.",
    "otp_banking": "Do not share any code. If you did not request it, call your bank on the number printed on the back of your card.",
    "job": "Find the company's official careers page yourself and contact them there. Never pay a deposit or share bank or Singpass details to get a job.",
    "ecommerce": "Only pay or receive payment inside the platform's official app. Do not click links sent by the buyer or seller.",
    "government": "Government agencies never ask you to transfer money or share bank log-in details by phone or message. Call the ScamShield helpline (1799) if unsure.",
    "investment": "Do not transfer money. Check whether the firm is licensed on the MAS website, typed in yourself.",
    "personal": "Contact the person on a number you already have saved, or call them, before sending money or codes.",
    "other": "Contact the organisation through its official app or a website you type in yourself.",
}
REPORT_LINE = "Report it in the ScamShield app or call the ScamShield helpline (1799)."


def _asks_for_code(text: str) -> bool:
    for rx in CODE_ASK_RES:
        for m in rx.finditer(text):
            verb = re.search(CODE_VERB, m.group(0), re.I)
            verb_pos = m.start() + verb.start()
            if not NEGATION_BEFORE.search(text[max(0, verb_pos - 25):verb_pos]):
                return True
    return False


def detect_risky_requests(text: str) -> set[str]:
    found = set()
    if URL_RE.search(text):
        found.add("click_link")
    if PHONE_RE.search(text):
        found.add("call_number")
    if MONEY_RE.search(text) and PAY_RE.search(text):
        found.add("pay_money")
    if _asks_for_code(text):
        found.add("share_code_or_password")
    if REPLY_RE.search(text):
        found.add("reply_with_details")
    if INSTALL_RE.search(text):
        found.add("install_app")
    if SAFE_ACCOUNT_RE.search(text):
        found.add("transfer_to_account")
    return found


def message_contacts(text: str) -> list[str]:
    """Links and phone numbers that appear in the message."""
    return [m.group(0) for m in URL_RE.finditer(text)] + [m.group(0) for m in PHONE_RE.finditer(text)]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().strip('"\'“”‘’').lower()


def find_span(text: str, phrase: str):
    p = _norm(phrase)
    if not p:
        return None
    low = re.sub(r"\s+", " ", text).lower()
    i = low.find(p)
    return (i, i + len(p)) if i >= 0 else None


def check_red_flags(red_flags: list[dict], text: str) -> list[dict]:
    """Annotate each red flag with whether its phrase and quote are real."""
    advisories = load_advisories()
    checked = []
    for rf in red_flags:
        span = find_span(text, rf.get("phrase", ""))
        adv = advisories.get(rf.get("advisory_id", ""))
        checked.append({**rf, "span": span, "phrase_verified": span is not None,
                        "quote_verified": quote_exists(rf.get("advisory_id", ""), rf.get("advisory_quote", "")),
                        "source_url": adv.source_url if adv else None,
                        "advisory_title": adv.title if adv else None})
    return checked


def apply_policy(verdict: dict, text: str) -> tuple[dict, list[str]]:
    """Return (final verdict, list of adjustments made by code)."""
    v = dict(verdict)
    notes = []
    risky = set(v.get("risky_requests", [])) | detect_risky_requests(text)
    v["risky_requests"] = sorted(risky)
    if v["tier"] == "looks_fine" and risky:
        v["tier"] = "verify_safe_route"
        notes.append("Raised from 'looks fine': the message asks you to "
                     + ", ".join(r.replace("_", " ") for r in sorted(risky)) + ".")
    step = v.get("safe_next_step", "") or ""
    contacts = message_contacts(text)
    uses_message_route = any(c.lower() in step.lower() for c in contacts) or re.search(
        r"\b(click|tap|open) (the|this) link\b|\bcall the number in\b", step, re.I)
    if v["tier"] != "looks_fine" and (uses_message_route or not step.strip()):
        v["safe_next_step"] = DEFAULT_STEPS.get(v.get("message_type", "other"), DEFAULT_STEPS["other"])
        if uses_message_route:
            notes.append("Replaced the suggested next step because it used the message's own link or number.")
    if v["tier"] == "looks_fine" and not v["safe_next_step"].strip():
        v["safe_next_step"] = "No action needed. If anything in it changes or asks you for money, a link or a code, check again."
    if v["tier"] == "likely_scam" and REPORT_LINE not in v["safe_next_step"]:
        v["safe_next_step"] = v["safe_next_step"].rstrip() + " " + REPORT_LINE
    return v, notes
