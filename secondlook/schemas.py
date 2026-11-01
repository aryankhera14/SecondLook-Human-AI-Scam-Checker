"""Typed outputs the agent must return (enforced by the SDK's structured output)."""
from typing import Literal

from pydantic import BaseModel

MessageType = Literal["delivery", "otp_banking", "job", "ecommerce", "government",
                      "investment", "personal", "other"]
ContextKey = Literal["expecting_delivery", "requested_otp_or_login", "applied_for_job",
                     "initiated_payment_or_refund", "knows_sender_personally",
                     "made_listing_selling_item", "has_account_with_named_org"]
RiskyRequest = Literal["click_link", "pay_money", "share_code_or_password", "install_app",
                       "call_number", "reply_with_details", "transfer_to_account"]
Tier = Literal["looks_fine", "verify_safe_route", "likely_scam", "cant_tell"]

TIER_LABELS = {
    "looks_fine": "Looks fine",
    "verify_safe_route": "Probably genuine - verify the safe way",
    "likely_scam": "Likely scam",
    "cant_tell": "Can't tell safely",
}
CONTEXT_QUESTIONS = {  # plain-language fallback wording for each context key
    "expecting_delivery": "Are you expecting a delivery right now?",
    "requested_otp_or_login": "Did you just try to log in, pay, or request a code yourself?",
    "applied_for_job": "Did you apply for this specific job or company?",
    "initiated_payment_or_refund": "Did you make this payment, transfer or refund request yourself?",
    "knows_sender_personally": "Do you know this person and recognise this number?",
    "made_listing_selling_item": "Are you currently selling this item online?",
    "has_account_with_named_org": "Do you have an account with the organisation named in the message?",
}


# ---- Memory policy (Idea 3). Set by the application, not the model. ----
# Only lasting situations may be remembered; one-off facts (an OTP request, a payment) never are.
# Default lifetime in days per fact type; the user can change it with one tap when saving.
MEMORY_LIFETIME_DAYS = {
    "expecting_delivery": 5,
    "made_listing_selling_item": 14,
    "applied_for_job": 30,
    "has_account_with_named_org": 90,
}
LIFETIME_CHOICES = [1, 5, 14, 30, 90]
# Cues in a GENUINE message that the remembered situation has ended (event-based forgetting).
COMPLETION_CUES = {
    "expecting_delivery": r"\b(has been delivered|was delivered|delivered to|successfully delivered|collected|picked up)\b",
    "made_listing_selling_item": r"\b(marked as sold|item (has been )?sold|listing (has been )?sold)\b",
    "applied_for_job": r"\b(offer letter|we regret|unsuccessful|position has been filled|not been selected)\b",
}
FORGET_PROMPTS = {
    "expecting_delivery": "Looks like your parcel has arrived. Forget \u201cexpecting a parcel\u201d?",
    "made_listing_selling_item": "Looks like your item has sold. Forget that you are selling it?",
    "applied_for_job": "Looks like this application has an outcome. Forget that you are applying?",
}
RECHECK_QUESTIONS = {
    "expecting_delivery": "Are you still expecting a parcel delivery?",
    "made_listing_selling_item": "Are you still selling this item online?",
    "applied_for_job": "Are you still waiting to hear back from job applications?",
    "has_account_with_named_org": "Do you still have an account with this organisation?",
}
FOCUS_MESSAGE_TYPES = {"delivery", "ecommerce", "otp_banking", "job"}  # the three focus scam types


class RedFlag(BaseModel):
    phrase: str           # must be copied exactly from the message
    reason: str
    advisory_id: str      # id of the advisory that supports it
    advisory_quote: str   # must be copied exactly from search_advisories output


class MemorySuggestion(BaseModel):
    fact: str             # plain sentence shown to the user, e.g. "I am expecting a Shopee parcel"
    context_key: ContextKey
    value: bool
    applies_to: list[MessageType]
    days_valid: int


class Verdict(BaseModel):
    message_type: MessageType
    risky_requests: list[RiskyRequest]
    tier: Tier
    summary: str
    red_flags: list[RedFlag]
    safe_next_step: str
    context_used: list[str]
    memory_suggestions: list[MemorySuggestion]


class BinaryVerdict(BaseModel):
    """Baseline output: the usual scam / not-scam answer."""
    is_scam: bool
    reason: str


def normalise_verdict(raw: dict) -> dict:
    """Coerce a model's JSON into a valid Verdict dict, dropping invalid parts.
    Raises ValueError when the essential field (tier) is missing or unusable."""
    from typing import get_args
    tiers, types = set(get_args(Tier)), set(get_args(MessageType))
    risky_ok, keys = set(get_args(RiskyRequest)), set(get_args(ContextKey))
    d = dict(raw)
    if "tier" not in d and isinstance(d.get("verdict"), str):
        d["tier"] = d["verdict"]
    tier = str(d.get("tier", "")).strip().lower().replace(" ", "_").replace("-", "_")
    tier = {"verify": "verify_safe_route", "scam": "likely_scam", "fine": "looks_fine",
            "unsure": "cant_tell", "cannot_tell": "cant_tell"}.get(tier, tier)
    if tier not in tiers:
        raise ValueError(f"model returned no valid tier: {d.get('tier')!r}")
    flags = []
    for f in d.get("red_flags") or []:
        if isinstance(f, dict) and f.get("phrase"):
            flags.append({k: str(f.get(k, "")) for k in ("phrase", "reason", "advisory_id", "advisory_quote")})
    sugg = []
    for m in d.get("memory_suggestions") or []:
        if isinstance(m, dict) and m.get("context_key") in keys:
            sugg.append({"fact": str(m.get("fact", "")), "context_key": m["context_key"],
                         "value": bool(m.get("value", True)),
                         "applies_to": [t for t in (m.get("applies_to") or []) if t in types],
                         "days_valid": int(m.get("days_valid") or 0) if str(m.get("days_valid", "")).isdigit() else 0})
    mtype = d.get("message_type") if d.get("message_type") in types else "other"
    return Verdict(message_type=mtype,
                   risky_requests=[r for r in (d.get("risky_requests") or []) if r in risky_ok],
                   tier=tier, summary=str(d.get("summary") or ""), red_flags=flags,
                   safe_next_step=str(d.get("safe_next_step") or ""),
                   context_used=[str(c) for c in (d.get("context_used") or [])],
                   memory_suggestions=sugg).model_dump()
