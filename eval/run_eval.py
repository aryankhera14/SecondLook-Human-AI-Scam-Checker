"""Benchmark for Ideas 1 and 2 (arena-style).

    python -m eval.run_eval                     # all 40 messages, all conditions
    python -m eval.run_eval --limit 6           # quick smoke run
    python -m eval.run_eval --repeats 3         # repeat to see model variability
    python -m eval.run_eval --resume runtime/results/<folder>   # finish missing/failed checks

Writes runtime/results/<timestamp>/records.jsonl and report.md
"""
import argparse
import asyncio
import datetime as dt
import json
import pathlib

from secondlook.agent import CONDITIONS, QuotaExhausted, run_check
from secondlook.config import DATA, MODEL, PROVIDER_LABEL, RUNTIME, use_mock

from .metrics import arena, derive_policy, summarise
from .simulated_user import answer_from_card

NOW = dt.datetime(2026, 10, 4, 20, 0)
FOCUS_TOPICS = ("delivery_ecommerce", "phishing", "job")
STOP = {"quota": False}


async def one(msg, condition, rep, sem):
    async with sem:
        if STOP["quota"]:
            return {"id": msg["id"], "condition": condition, "rep": rep, "label": msg["label"],
                    "category": msg["category"], "topic": msg.get("topic", ""), "error": "NotRun: daily quota reached"}
        try:
            res = await run_check(msg, condition, lambda q: answer_from_card(q, msg["context"]), now=NOW)
            v = res["verdict"]
            rf = res["red_flags"]
            return {"id": msg["id"], "condition": condition, "rep": rep, "label": msg["label"],
                    "category": msg["category"], "topic": msg.get("topic", ""), "tier": v["tier"], "raw_tier": res["raw_tier"],
                    "risky": v["risky_requests"], "n_questions": len(res["questions"]),
                    "question_keys": [q["context_key"] for q in res["questions"]],
                    "red_flags": len(rf), "phrases_verified": sum(f["phrase_verified"] for f in rf),
                    "quotes_verified": sum(f["quote_verified"] for f in rf),
                    "adjustments": res["adjustments"], "summary": v["summary"],
                    "recovered": res.get("recovered", False), "tokens": res["tokens"], "error": None}
        except QuotaExhausted as e:
            STOP["quota"] = True
            return {"id": msg["id"], "condition": condition, "rep": rep, "label": msg["label"],
                    "category": msg["category"], "topic": msg.get("topic", ""), "error": f"QuotaExhausted: {e}"}
        except Exception as e:  # keep going; errors are reported, never hidden
            return {"id": msg["id"], "condition": condition, "rep": rep, "label": msg["label"],
                    "category": msg["category"], "topic": msg.get("topic", ""), "error": f"{type(e).__name__}: {e}"}


def table(rows, cols):
    head = "| " + " | ".join(c for c, _ in cols) + " |\n|" + "---|" * len(cols) + "\n"
    return head + "".join("| " + " | ".join(f(r) for _, f in cols) + " |\n" for r in rows)


def pct(a, b):
    return f"{a:.0f}/{b:.0f}" if b else "-"


def report(all_records, errors, args, out):
    mock = use_mock()
    conds = sorted({r["condition"] for r in all_records} | {e["condition"] for e in errors})
    valid = {}
    for r in all_records:
        valid.setdefault(r["condition"], set()).add((r["id"], r["rep"]))
    matched = set.intersection(*valid.values()) if valid and len(valid) == len(conds) else set()
    records = [r for r in all_records if (r["id"], r["rep"]) in matched]
    coverage = " · ".join(f"{c}: {len(valid.get(c, ()))}" for c in conds)
    lines = [f"# SecondLook evaluation report\n",
             f"{'**MOCK MODE: rule-based stand-in model. These numbers test the pipeline and are NOT results.**' if mock else f'Model: `{MODEL}`'}  ",
             f"Run: {dt.datetime.now():%Y-%m-%d %H:%M} · repeats: {args.repeats} · errors: {len(errors)}  ",
             f"Valid checks per condition: {coverage}  ",
             f"**All tables below use the {len({i for i, _ in matched})} messages that every condition answered "
             f"(matched comparison).** Answers recovered from a malformed final tool call: "
             f"{sum(r.get('recovered', False) for r in all_records)}.\n"]
    s = summarise(records)
    cols = [("Condition", lambda r: r[0]), ("Mean outcome score", lambda r: f"{r[1]['mean_score']:.2f}"),
            ("Missed scams", lambda r: pct(r[1]['missed_scam'], r[1]['scams'])),
            ("Unsafe outcomes", lambda r: pct(r[1]['unsafe_outcome'], r[1]['scams'])),
            ("False alarms", lambda r: pct(r[1]['false_alarm'], r[1]['legit'])),
            ("Questions / msg", lambda r: f"{r[1]['questions_per_msg']:.2f}"),
            ("Tokens", lambda r: f"{r[1]['tokens']:.0f}")]
    lines += ["## Idea 1: does asking for context help? (all messages)\n", table(sorted(s.items()), cols)]
    for cat in ("context_dependent", "context_fits_scam", "clear_scam", "clear_legit"):
        sub = [r for r in records if r["category"] == cat]
        if sub:
            lines += [f"\n### Category: {cat}\n", table(sorted(summarise(sub).items()), cols[:6])]
    focus = [r for r in records if r["topic"] in FOCUS_TOPICS or r["topic"] == "everyday"]
    lines += ["\n## Focus scope: delivery & e-commerce, phishing, job (+ everyday genuine messages)\n",
              "Out-of-scope scams (government impersonation, investment, friend impersonation) are excluded here.\n",
              table(sorted(summarise(focus).items()), cols[:6])]
    for topic in ("delivery_ecommerce", "phishing", "job", "out_of_scope", "everyday"):
        sub = [r for r in records if r["topic"] == topic]
        if sub:
            lines += [f"\n### Scam type: {topic}\n", table(sorted(summarise(sub).items()), cols[:6])]
    board, matches = arena(records)
    lines += ["\n## Arena: head-to-head on the same messages\n",
              table(board, [("Rank", lambda r: str(board.index(r) + 1)), ("Condition", lambda r: r["name"]),
                            ("Wins", lambda r: str(r["wins"])), ("Losses", lambda r: str(r["losses"])), ("Ties", lambda r: str(r["ties"]))]),
              "\n" + table(matches, [("Match", lambda m: f"{m['a']} vs {m['b']}"),
                                     ("Result", lambda m: f"{m['a_wins']}-{m['b_wins']} ({m['ties']} ties)")])]
    sl = [r for r in records if r["condition"] == "secondlook"]
    if sl:
        derived = [dict(r, policy=p, tier=derive_policy(r["tier"], p)) for r in sl
                   for p in ("always_cautious", "binary", "tiered")]
        s2 = summarise(derived, key="policy")
        lines += ["\n## Idea 2: verdict design (same SecondLook judgements, three ways of showing them)\n",
                  table(sorted(s2.items()), cols[:5] + [("Friction on harmless legit msgs", lambda r: pct(r[1]['friction'], r[1]['legit']))])]
        b2, m2 = arena(derived, key="policy")
        lines += ["\n" + table(b2, [("Policy", lambda r: r["name"]), ("Wins", lambda r: str(r["wins"])),
                                     ("Losses", lambda r: str(r["losses"])), ("Ties", lambda r: str(r["ties"]))])]
        nflags = sum(r["red_flags"] for r in sl)
        lines += [f"\n### Evidence checks (SecondLook)\n",
                  f"Red-flag phrases found verbatim in the message: {pct(sum(r['phrases_verified'] for r in sl), nflags)}  ",
                  f"Advisory quotes found verbatim in the corpus: {pct(sum(r['quotes_verified'] for r in sl), nflags)}  ",
                  f"Verdicts changed by code guardrails: {sum(r['tier'] != r['raw_tier'] for r in sl)}/{len(sl)}\n"]
    if errors:
        lines += ["\n## Errors (resume with `--resume` to retry these)\n"] + [
            f"- {e['condition']} {e['id']}: {e['error'][:300]}" for e in errors]
    (out / "report.md").write_text("\n".join(lines))


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conditions", nargs="+", default=list(CONDITIONS))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ids", nargs="+")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--concurrency", type=int, default=4 if use_mock() else 1)
    ap.add_argument("--resume", help="results folder to complete: keeps valid checks, reruns the rest")
    args = ap.parse_args()
    msgs = json.loads((DATA / "messages.json").read_text())
    if args.ids:
        msgs = [m for m in msgs if m["id"] in args.ids]
    if args.limit:
        msgs = msgs[:args.limit]
    kept = []
    if args.resume:
        out = pathlib.Path(args.resume)
        old = [json.loads(l) for l in (out / "records.jsonl").read_text().splitlines() if l.strip()]
        kept = [r for r in old if not r.get("error")]
    else:
        out = RUNTIME / "results" / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        out.mkdir(parents=True)
    done = {(r["id"], r["condition"], r["rep"]) for r in kept}
    sem = asyncio.Semaphore(args.concurrency)
    tasks = [one(m, c, r, sem) for r in range(args.repeats) for m in msgs for c in args.conditions
             if (m["id"], c, r) not in done]
    print(f"Running {len(tasks)} checks ({'MOCK' if use_mock() else MODEL}); keeping {len(kept)} from before...")
    rows = kept + list(await asyncio.gather(*tasks))
    with open(out / "records.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    records = [r for r in rows if not r["error"]]
    errors = [r for r in rows if r["error"]]
    report(records, errors, args, out)
    print((out / "report.md").read_text())
    print(f"\nSaved to {out}")
    if STOP["quota"]:
        print(f"\nDaily token limit reached. Run this again tomorrow to finish:\n"
              f"    python -m eval.run_eval --resume \"{out}\"")


if __name__ == "__main__":
    asyncio.run(main())
