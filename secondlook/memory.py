"""Scoped, expiring memory with consent (Idea 3) - with adaptive forgetting.

Nothing is stored unless `add` is called, and the app only calls it after the user
clicks Save. Only lasting situations can be stored (see MEMORY_LIFETIME_DAYS).

How SecondLook forgets, without the user having to manage it:
  1. Default lifetime per fact type, set by the app (e.g. a parcel: 5 days).
  2. Event-based: a genuine message that ends the situation ("has been delivered")
     triggers a one-tap "Forget this?" offer.
  3. Re-check before relaxing caution: a remembered fact older than 48 hours is not
     trusted silently when the message asks for money, a link or a code - the app
     asks "Still expecting a parcel?" first. Yes renews it, No forgets it.
  4. Contradiction: any answer that conflicts with a remembered fact replaces it.
  5. Manual delete in the sidebar.

Modes (for the evaluation): "off" stores nothing; "permanent" never forgets;
"expiring" uses lifetimes only (layer 1); "adaptive" uses all layers (the app default).
"""
import datetime as dt
import json
import re
import uuid
from dataclasses import asdict, dataclass

from .schemas import COMPLETION_CUES, FORGET_PROMPTS, MEMORY_LIFETIME_DAYS

MODES = ("off", "permanent", "expiring", "adaptive")
RECHECK_AFTER_HOURS = 48
DEFAULT_SCOPE = {  # which message types each remembered fact applies to (set by the app)
    "expecting_delivery": ["delivery", "ecommerce"],
    "made_listing_selling_item": ["ecommerce"],
    "applied_for_job": ["job"],
    "has_account_with_named_org": ["otp_banking"],
}
SAFE_TIERS_FOR_EVENTS = ("looks_fine", "verify_safe_route")  # a scam can't make SecondLook forget


@dataclass
class MemoryItem:
    id: str
    fact: str
    context_key: str
    value: bool
    applies_to: list
    created: str
    expires: str | None
    last_confirmed: str | None = None

    def is_active(self, now: dt.datetime) -> bool:
        return self.expires is None or now < dt.datetime.fromisoformat(self.expires)

    def age_hours(self, now: dt.datetime) -> float:
        since = dt.datetime.fromisoformat(self.last_confirmed or self.created)
        return (now - since).total_seconds() / 3600


class MemoryStore:
    def __init__(self, path=None, mode: str = "adaptive"):
        assert mode in MODES, mode
        self.path, self.mode = path, mode
        self.items: list[MemoryItem] = []
        if path and path.exists():
            for d in json.loads(path.read_text()):
                if d.get("context_key") in MEMORY_LIFETIME_DAYS:  # drop invalid legacy entries
                    self.items.append(MemoryItem(**{k: d.get(k) for k in MemoryItem.__dataclass_fields__}))
            self._save()

    # ---------- storage ----------
    def _save(self):
        if self.path:
            self.path.write_text(json.dumps([asdict(i) for i in self.items], indent=2))

    def _expiry(self, key: str, now: dt.datetime, days: int | None) -> str | None:
        if self.mode == "permanent":
            return None
        return (now + dt.timedelta(days=days or MEMORY_LIFETIME_DAYS[key])).isoformat()

    def add(self, suggestion: dict, now: dt.datetime, days: int | None = None) -> MemoryItem | None:
        """Store an approved suggestion. Returns None if this kind of fact may not be remembered."""
        key = suggestion.get("context_key")
        if self.mode == "off" or key not in MEMORY_LIFETIME_DAYS:
            return None
        self.items = [i for i in self.items if i.context_key != key]
        item = MemoryItem(uuid.uuid4().hex[:8], suggestion["fact"], key, bool(suggestion.get("value", True)),
                          DEFAULT_SCOPE[key], now.isoformat(), self._expiry(key, now, days), now.isoformat())
        self.items.append(item)
        self._save()
        return item

    def active(self, now: dt.datetime, message_type: str | None = None) -> list[MemoryItem]:
        if self.mode == "off":
            return []
        return [i for i in self.items if i.is_active(now)
                and (message_type is None or message_type in i.applies_to)]

    def get(self, item_id: str) -> MemoryItem | None:
        return next((i for i in self.items if i.id == item_id), None)

    def delete(self, item_id: str):
        self.items = [i for i in self.items if i.id != item_id]
        self._save()

    def clear(self):
        self.items = []
        self._save()

    # ---------- adaptive forgetting ----------
    def confirm(self, item_id: str, now: dt.datetime):
        """The person re-confirmed the fact: renew it for a full lifetime."""
        item = self.get(item_id)
        if item:
            item.last_confirmed = now.isoformat()
            item.expires = self._expiry(item.context_key, now, None)
            self._save()

    def needs_recheck(self, item: MemoryItem, now: dt.datetime, risky: bool) -> bool:
        """Layer 3: an old fact may not relax caution on a risky message without a re-check."""
        return (self.mode == "adaptive" and risky and item.value is True
                and item.age_hours(now) > RECHECK_AFTER_HOURS)

    def apply_answer(self, context_key: str, answer: bool | None, now: dt.datetime) -> str | None:
        """Layer 4: an answer that matches a fact renews it; one that conflicts forgets it."""
        if answer is None or self.mode == "off":
            return None
        for item in [i for i in self.items if i.context_key == context_key and i.is_active(now)]:
            if item.value == answer:
                if self.mode == "adaptive":
                    self.confirm(item.id, now)
                    return "renewed"
                return None
            self.delete(item.id)
            return "forgotten"
        return None

    def completion_offers(self, text: str, tier: str, now: dt.datetime) -> list[dict]:
        """Layer 2: a genuine message that ends a remembered situation -> offer to forget it."""
        if self.mode != "adaptive" or tier not in SAFE_TIERS_FOR_EVENTS:
            return []
        offers = []
        for item in self.active(now):
            cue = COMPLETION_CUES.get(item.context_key)
            if cue and re.search(cue, text, re.I):
                offers.append({"item_id": item.id, "context_key": item.context_key, "fact": item.fact,
                               "prompt": FORGET_PROMPTS[item.context_key]})
        return offers
