"""Code-graded metrics. Every number comes from labels fixed before any run."""
from collections import defaultdict

SAFE_TIERS = {"likely_scam", "cant_tell", "verify_safe_route"}  # none of these tell you to act on the message


def outcome_score(label: str, tier: str, risky: list) -> float:
    """1 = best possible outcome for the person, 0 = worst."""
    if label == "scam":
        return {"likely_scam": 1.0, "cant_tell": 0.75, "verify_safe_route": 0.5, "looks_fine": 0.0}[tier]
    if tier == "looks_fine":
        return 1.0
    if tier == "verify_safe_route":
        return 1.0 if risky else 0.75  # extra friction only matters if nothing risky was asked
    return {"cant_tell": 0.25, "likely_scam": 0.0}[tier]


def flags(label: str, tier: str, risky: list) -> dict:
    return {
        "missed_scam": label == "scam" and tier in ("looks_fine", "verify_safe_route"),
        "unsafe_outcome": label == "scam" and tier == "looks_fine",
        "false_alarm": label == "legit" and tier in ("likely_scam", "cant_tell"),
        "friction": label == "legit" and not risky and tier != "looks_fine",
    }


def derive_policy(tier: str, policy: str) -> str:
    """Idea 2: the same SecondLook judgement shown through three verdict designs."""
    if policy == "tiered":
        return tier
    if policy == "binary":  # 'scam' or 'not scam'; 'not scam' means the person acts on the message
        return "likely_scam" if tier in ("likely_scam", "cant_tell") else "looks_fine"
    if policy == "always_cautious":  # never says a message is fine
        return "likely_scam" if tier == "likely_scam" else "cant_tell"
    raise ValueError(policy)


def summarise(records: list[dict], key: str = "condition") -> dict:
    out = defaultdict(lambda: defaultdict(float))
    for r in records:
        s = out[r[key]]
        s["n"] += 1
        s["scams"] += r["label"] == "scam"
        s["legit"] += r["label"] == "legit"
        for k, v in flags(r["label"], r["tier"], r["risky"]).items():
            s[k] += v
        s["score"] += outcome_score(r["label"], r["tier"], r["risky"])
        s["questions"] += r.get("n_questions", 0)
        s["tokens"] += r.get("tokens", 0)
    for s in out.values():
        s["mean_score"] = s["score"] / s["n"]
        s["questions_per_msg"] = s["questions"] / s["n"]
    return {k: dict(v) for k, v in out.items()}


def arena(records: list[dict], key: str = "condition") -> list[dict]:
    """Head-to-head: on each shared message, the condition with the better outcome wins."""
    by_msg = defaultdict(dict)
    for r in records:
        by_msg[r["id"]][r[key]] = outcome_score(r["label"], r["tier"], r["risky"])
    names = sorted({r[key] for r in records})
    table = {n: {"wins": 0, "losses": 0, "ties": 0} for n in names}
    matches = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            w = l = t = 0
            for scores in by_msg.values():
                if a in scores and b in scores:
                    if scores[a] > scores[b]: w += 1
                    elif scores[a] < scores[b]: l += 1
                    else: t += 1
            matches.append({"a": a, "b": b, "a_wins": w, "b_wins": l, "ties": t})
            table[a]["wins"] += w; table[a]["losses"] += l; table[a]["ties"] += t
            table[b]["wins"] += l; table[b]["losses"] += w; table[b]["ties"] += t
    board = sorted(({"name": n, **v} for n, v in table.items()), key=lambda x: (-x["wins"], x["losses"]))
    return board, matches
