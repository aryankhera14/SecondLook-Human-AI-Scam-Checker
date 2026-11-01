"""Local corpus of official advisory text and a simple keyword search over it."""
import re
from dataclasses import dataclass
from functools import lru_cache

from .config import DATA

STOP = set("the a an to of and or in on for is are be you your with by it this that as at from if not "
           "will would can any all".split())


@dataclass(frozen=True)
class Advisory:
    id: str
    title: str
    source_url: str
    applies_to: tuple
    lines: tuple


def _tokens(text: str) -> set:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOP and len(t) > 2}


@lru_cache(maxsize=1)
def load_advisories() -> dict:
    out = {}
    for path in sorted((DATA / "advisories").glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        _, front, body = raw.split("---", 2)
        meta = dict(line.split(":", 1) for line in front.strip().splitlines())
        meta = {k.strip(): v.strip() for k, v in meta.items()}
        lines = tuple(l.strip() for l in body.strip().splitlines() if l.strip())
        out[meta["id"]] = Advisory(meta["id"], meta["title"], meta["source_url"],
                                   tuple(a.strip() for a in meta["applies_to"].split(",")), lines)
    return out


def search(query: str, message_type: str | None = None, k: int = 4) -> list[dict]:
    """Return the k advisory lines that best match the query (exact text, for quoting)."""
    q = _tokens(query)
    scored = []
    for adv in load_advisories().values():
        bonus = 1.5 if message_type and message_type in adv.applies_to else 0.0
        for line in adv.lines:
            overlap = len(q & _tokens(line))
            if overlap or bonus:
                scored.append((overlap + bonus, adv, line))
    scored.sort(key=lambda x: -x[0])
    return [{"advisory_id": a.id, "title": a.title, "source_url": a.source_url, "quote": line}
            for _, a, line in scored[:k]]


def quote_exists(advisory_id: str, quote: str) -> bool:
    adv = load_advisories().get(advisory_id)
    if not adv or not quote.strip():
        return False
    norm = lambda s: re.sub(r"\s+", " ", s.strip().strip('"\'').lower())
    q = norm(quote)
    return any(q in norm(line) for line in adv.lines)
