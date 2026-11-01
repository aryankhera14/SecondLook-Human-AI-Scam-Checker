"""Benchmark for Idea 3: when should SecondLook forget?

    python -m eval.memory_eval

Compares four memory modes on a 15-day scenario (data/memory_scenario.json):
  off        - no memory: asks every time
  permanent  - never forgets
  expiring   - default lifetime only (fixed expiry)
  adaptive   - lifetime + 'forget this?' after a genuine ending event + re-check before an old
               fact relaxes caution + contradiction (the app's default)
The simulated person answers truthfully from each session's context card, approves every memory
suggestion, and accepts a 'forget this?' offer only if that situation really ended.
"""
import asyncio
import datetime as dt
import json

import argparse

from secondlook.agent import QuotaExhausted, run_check
from secondlook.config import DATA, MODEL, PROVIDER_LABEL, RUNTIME, use_mock
from secondlook.memory import MODES, MemoryStore

from .metrics import outcome_score
from .simulated_user import answer_from_card

START = dt.datetime(2026, 10, 5, 9, 0)


async def run_mode(mode: str, scenario: dict) -> list[dict]:
    store = MemoryStore(mode=mode)
    rows = []
    for s in scenario["sessions"]:
        now = START + dt.timedelta(days=s["day"])
        msg = {"id": s["id"], "text": s["text"], "channel": "SMS", "sender": ""}
        before = {i.context_key: i.value for i in store.active(now)}
        try:
            res = await run_check(msg, "secondlook", lambda q: answer_from_card(q, s["context"]), memory=store,
                                  now=now, forget_fn=lambda o: o["context_key"] in s.get("completes", []))
        except QuotaExhausted:
            raise
        except Exception as e:
            rows.append({"mode": mode, "day": s["day"], "id": s["id"], "error_msg": str(e)})
            continue
        v = res["verdict"]
        for sug in v["memory_suggestions"]:  # simulated consent: approve each suggestion
            store.add(sug, now)
        stale_held = any(s["context"].get(k) is not None and s["context"][k] != val for k, val in before.items())
        score = outcome_score(s["label"], v["tier"], v["risky_requests"])
        rows.append({"mode": mode, "day": s["day"], "id": s["id"], "label": s["label"], "tier": v["tier"],
                     "questions": sum(q.get("kind") != "recheck" for q in res["questions"]),
                     "rechecks": sum(q.get("kind") == "recheck" for q in res["questions"]),
                     "forget_taps": len(res["forget_offers"]),
                     "wrong": score < 1.0, "stale_memory_held": stale_held,
                     "stale_error": stale_held and score < 1.0 and s["label"] == "scam",
                     "events": res["memory_events"], "tokens": res["tokens"], "error_msg": None})
    return rows


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", nargs="+", default=list(MODES), choices=MODES,
                    help="run only some modes (e.g. to split the run across days on Groq's free tier)")
    args = ap.parse_args()
    scenario = json.loads((DATA / "memory_scenario.json").read_text())
    rows = []
    for mode in args.modes:
        try:
            rows += await run_mode(mode, scenario)
        except QuotaExhausted:
            print(f"Daily token limit reached during mode '{mode}'. That mode and any after it did not complete; "
                  f"rerun tomorrow with: python -m eval.memory_eval --modes {' '.join(args.modes[args.modes.index(mode):])}")
            break
    out = RUNTIME / "results"
    out.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    (out / f"memory-{stamp}.json").write_text(json.dumps(rows, indent=2))
    print("MOCK MODE: pipeline test only, not results.\n" if use_mock() else f"Model: {MODEL} ({PROVIDER_LABEL})\n")
    print("| Memory mode | Questions | Re-checks | 'Forget?' taps | Wrong outcomes | Scams misjudged because of stale memory | Errors |")
    print("|---|---|---|---|---|---|---|")
    ran = [m for m in args.modes if any(x["mode"] == m for x in rows)]
    if not ran:
        print("| (no mode completed) | | | | | | |")
    for mode in ran:
        r = [x for x in rows if x["mode"] == mode and not x["error_msg"]]
        errs = sum(1 for x in rows if x["mode"] == mode and x["error_msg"])
        print(f"| {mode} | {sum(x['questions'] for x in r)} | {sum(x['rechecks'] for x in r)} | "
              f"{sum(x['forget_taps'] for x in r)} | {sum(x['wrong'] for x in r)}/{len(r)} | "
              f"{sum(x['stale_error'] for x in r)} | {errs} |")
    print("\nPer session:")
    for x in rows:
        if x["error_msg"]:
            print(f"  {x['mode']:9} day {x['day']:>2} {x['id']} ERROR {x['error_msg'][:80]}")
        else:
            print(f"  {x['mode']:9} day {x['day']:>2} {x['id']} {x['label']:5} -> {x['tier']:17} "
                  f"q={x['questions']} recheck={x['rechecks']} {'; '.join(x['events'])}")
    print(f"\nSaved to {out / f'memory-{stamp}.json'}")


if __name__ == "__main__":
    asyncio.run(main())
