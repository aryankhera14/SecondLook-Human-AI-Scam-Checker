"""Ablation for Idea 1: does contextual clarification help, holding everything else fixed?

    python -m eval.ablation_clarification                    # run both conditions on all 40 messages
    python -m eval.ablation_clarification --resume <folder>  # finish a run cut off by the daily limit
    python -m eval.ablation_clarification --analyse <folder> # rebuild the outputs from saved results

Condition A (clarification): the full SecondLook system, as in the main benchmark.
Condition B (no_clarification): the same system with clarification removed:
  - the ask_user tool is not offered, and a stray ask_user call is refused by the application;
  - the question limit is 0, so the app cannot pause for a re-check either;
  - no simulated person is attached, so no context card can reach the model;
  - step 4 of the instructions says it cannot ask (SECONDLOOK_NO_ASK_INSTRUCTIONS in prompts.py).
Everything else is identical: model, temperature, reasoning effort, sampling settings, advisories, tiers,
code-enforced rules (guardrails), evidence checks, dataset, labels, scoring and memory (off in both).

The two conditions are run back to back for each message (order alternates A-B / B-A), so a run that
stops at the daily token limit still leaves complete pairs. Results are saved after every check.
Outputs go to runtime/results/ablation_clarification/<timestamp>/ and never touch earlier results.
"""
import argparse
import asyncio
import csv
import datetime as dt
import difflib
import json
import math
import pathlib
import random
import sys

from secondlook import agent
from secondlook.agent import QuotaExhausted, run_check
from secondlook.config import (DATA, MODEL, PROVIDER_LABEL, REASONING_EFFORT, RUNTIME, TEMPERATURE,
                               use_mock)
from secondlook.memory import MemoryStore
from secondlook.prompts import SECONDLOOK_INSTRUCTIONS, SECONDLOOK_NO_ASK_INSTRUCTIONS

from .metrics import flags, outcome_score
from .simulated_user import answer_from_card

NOW = dt.datetime(2026, 10, 4, 20, 0)  # same date as the main benchmark
CONDITIONS = ("clarification", "no_clarification")
LABEL = {"clarification": "A: SecondLook (clarification)", "no_clarification": "B: SecondLook without clarification"}
OUT_ROOT = RUNTIME / "results" / "ablation_clarification"
DEFAULT_REFERENCE = RUNTIME / "results" / "20261101-005051"  # the 1 Nov main benchmark (for the noise check)


def wtext(path: pathlib.Path, text: str):
    """Always UTF-8: Windows would otherwise use cp1252 and fail on characters such as a non-breaking hyphen."""
    path.write_text(text, encoding="utf-8")


def no_answers(question):
    """Condition B never has a person to ask. If this is ever called, the check fails loudly."""
    raise AssertionError("Condition B tried to obtain a user answer.")


# ---------------------------------------------------------------- running
async def run_one(msg: dict, condition: str) -> dict:
    base = {"id": msg["id"], "condition": condition, "label": msg["label"], "category": msg["category"],
            "topic": msg.get("topic", ""), "pair_id": msg.get("pair_id")}
    clar = condition == "clarification"
    try:
        res = await run_check(msg, "secondlook",
                              (lambda q: answer_from_card(q, msg["context"])) if clar else no_answers,
                              memory=MemoryStore(mode="off"), now=NOW, clarification=clar)
    except QuotaExhausted:
        raise
    except Exception as e:  # recorded, never counted as a verdict
        return {**base, "error": f"{type(e).__name__}: {e}", "finished": f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}"}
    v = res["verdict"]
    rf = res["red_flags"]
    return {**base, "tier": v["tier"], "raw_tier": res["raw_tier"], "risky": v["risky_requests"],
            "n_questions": len(res["questions"]),
            "questions": [{"question": q.get("question"), "context_key": q.get("context_key"),
                           "kind": q.get("kind"), "answer": q.get("answer")} for q in res["questions"]],
            "adjustments": res["adjustments"], "summary": v["summary"], "context_used": v.get("context_used", []),
            "red_flags": len(rf), "phrases_verified": sum(f["phrase_verified"] for f in rf),
            "quotes_verified": sum(f["quote_verified"] for f in rf),
            "recovered": res.get("recovered", False), "tokens": res["tokens"], "error": None,
            "finished": f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}"}


def load(out: pathlib.Path) -> list[dict]:
    f = out / "results.jsonl"
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()] if f.exists() else []


def save(out: pathlib.Path, rows: list[dict]):
    with open(out / "results.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


async def run(out: pathlib.Path, msgs: list[dict], seed: int | None) -> bool:
    agent.set_seed(seed)
    rows = load(out)
    done = {(r["id"], r["condition"]) for r in rows if not r.get("error")}
    rows = [r for r in rows if not r.get("error")]  # failed checks are retried
    todo = []
    for i, m in enumerate(msgs):
        order = CONDITIONS if i % 2 == 0 else CONDITIONS[::-1]  # alternate A-B / B-A
        todo += [(m, c) for c in order if (m["id"], c) not in done]
    print(f"Running {len(todo)} checks ({'MOCK' if use_mock() else MODEL}); keeping {len(done)} valid from before.")
    for n, (m, c) in enumerate(todo, 1):
        try:
            r = await run_one(m, c)
        except QuotaExhausted as e:
            save(out, rows)
            print(f"\nDaily token limit reached after {n - 1} new checks: {str(e)[:160]}\n"
                  f"Nothing is lost. Finish later with:\n    python -m eval.ablation_clarification --resume \"{out}\"")
            return False
        rows.append(r)
        save(out, rows)
        status = r["error"][:70] if r.get("error") else f"{r['tier']:17} q={r['n_questions']} tokens={r['tokens']}"
        print(f"[{n:>2}/{len(todo)}] {m['id']:6} {c:16} {status}")
    info = json.loads((out / "run_info.json").read_text(encoding="utf-8"))
    info["seed_supported"] = (False if agent._SETTINGS["seed_supported"] is False
                              else "not set" if seed is None else "accepted by the API (no error)")
    info["finished"] = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}"
    wtext(out / "run_info.json", json.dumps(info, indent=2))
    return True


# ---------------------------------------------------------------- analysis
def binom_two_sided(k: int, n: int) -> float:
    """Exact two-sided sign test / McNemar test on n discordant pairs, k in one direction."""
    if n == 0:
        return 1.0
    lo = min(k, n - k)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(lo + 1)) / 2 ** n)


def metrics(rows: list[dict]) -> dict:
    scams = [r for r in rows if r["label"] == "scam"]
    legit = [r for r in rows if r["label"] == "legit"]
    f = [flags(r["label"], r["tier"], r["risky"]) for r in rows]
    n = len(rows)
    return {"messages": n, "scams": len(scams), "genuine": len(legit),
            "missed_scams": sum(x["missed_scam"] for x in f),
            "unsafe_outcomes": sum(x["unsafe_outcome"] for x in f),
            "false_alarms": sum(x["false_alarm"] for x in f),
            "friction": sum(x["friction"] for x in f),
            "questions_total": sum(r["n_questions"] for r in rows),
            "questions_per_msg": round(sum(r["n_questions"] for r in rows) / n, 2) if n else 0,
            "messages_with_a_question": sum(r["n_questions"] > 0 for r in rows),
            "mean_outcome_score": round(sum(outcome_score(r["label"], r["tier"], r["risky"]) for r in rows) / n, 3) if n else 0,
            "mean_tokens_per_check": round(sum(r["tokens"] for r in rows) / n) if n else 0,
            "verdicts_changed_by_code_rules": sum(r["tier"] != r["raw_tier"] for r in rows),
            "answers_recovered_from_malformed_tool_call": sum(bool(r.get("recovered")) for r in rows)}


def paired_bootstrap(pairs: list[tuple[float, float]], iters: int = 10000, seed: int = 619) -> tuple[float, float, float]:
    """95% percentile interval for the mean per-message score difference (A - B), resampling messages."""
    if not pairs:
        return 0.0, 0.0, 0.0
    rng = random.Random(seed)
    d = [a - b for a, b in pairs]
    means = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(iters))
    return sum(d) / len(d), means[int(0.025 * iters)], means[int(0.975 * iters) - 1]


def fmt_p(p: float) -> str:
    return "< 0.001" if p < 0.001 else f"= {p:.3f}"


def table(header: list[str], rows: list[list]) -> str:
    return ("| " + " | ".join(header) + " |\n|" + "---|" * len(header) + "\n" +
            "".join("| " + " | ".join(str(c) for c in r) + " |\n" for r in rows))


def analyse(out: pathlib.Path, reference: pathlib.Path | None):
    msgs = json.loads((DATA / "messages.json").read_text(encoding="utf-8"))
    order = [m["id"] for m in msgs]
    rows = load(out)
    info = json.loads((out / "run_info.json").read_text(encoding="utf-8")) if (out / "run_info.json").exists() else {}
    valid = {(r["id"], r["condition"]): r for r in rows if not r.get("error")}
    errors = [r for r in rows if r.get("error")]
    both = [i for i in order if (i, "clarification") in valid and (i, "no_clarification") in valid]
    A = {i: valid[(i, "clarification")] for i in both}
    B = {i: valid[(i, "no_clarification")] for i in both}
    mock = info.get("mock", use_mock())

    # ---- summary CSV (all matched messages + context-dependent subset + other categories)
    subsets = [("all", both), ("context_dependent", [i for i in both if A[i]["category"] == "context_dependent"]),
               ("context_fits_scam", [i for i in both if A[i]["category"] == "context_fits_scam"]),
               ("clear_scam", [i for i in both if A[i]["category"] == "clear_scam"]),
               ("clear_legit", [i for i in both if A[i]["category"] == "clear_legit"])]
    summary = []
    for name, ids in subsets:
        for c, src in (("clarification", A), ("no_clarification", B)):
            summary.append({"subset": name, "condition": c, **metrics([src[i] for i in ids])})
    with open(out / "summary.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader()
        w.writerows(summary)

    # ---- paired comparison
    paired = []
    for i in both:
        a, b = A[i], B[i]
        sa, sb = outcome_score(a["label"], a["tier"], a["risky"]), outcome_score(b["label"], b["tier"], b["risky"])
        change = "improved" if sa > sb else "worsened" if sa < sb else "unchanged"
        paired.append({"id": i, "label": a["label"], "category": a["category"], "topic": a["topic"],
                       "A_tier": a["tier"], "B_tier": b["tier"], "A_score": sa, "B_score": sb,
                       "change_with_clarification": change, "A_asked": a["n_questions"],
                       "A_questions": " | ".join(f"{q['context_key']}={q['answer']}" for q in a["questions"]),
                       "A_code_rule_changed": a["tier"] != a["raw_tier"], "B_code_rule_changed": b["tier"] != b["raw_tier"],
                       "A_raw_tier": a["raw_tier"], "B_raw_tier": b["raw_tier"]})
    with open(out / "paired_comparison.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(paired[0].keys()) if paired else ["id"])
        w.writeheader()
        w.writerows(paired)

    def counts(ps):
        return {k: sum(p["change_with_clarification"] == k for p in ps) for k in ("improved", "worsened", "unchanged")}

    def discordant(ps, key):  # McNemar on a binary flag: (A has it, B not) vs (B has it, A not)
        fa = lambda p, s: flags(p["label"], p[f"{s}_tier"], (A if s == "A" else B)[p["id"]]["risky"])[key]
        only_a = sum(fa(p, "A") and not fa(p, "B") for p in ps)
        only_b = sum(fa(p, "B") and not fa(p, "A") for p in ps)
        return only_a, only_b, binom_two_sided(only_a, only_a + only_b)

    cd = [p for p in paired if p["category"] == "context_dependent"]
    stats = {}
    for name, ps in (("all", paired), ("context_dependent", cd)):
        c = counts(ps)
        mean, lo, hi = paired_bootstrap([(p["A_score"], p["B_score"]) for p in ps])
        stats[name] = {**c, "improved_with_question": sum(p["change_with_clarification"] == "improved" and p["A_asked"] > 0 for p in ps),
                       "worsened_with_question": sum(p["change_with_clarification"] == "worsened" and p["A_asked"] > 0 for p in ps),
                       "sign_test_p": binom_two_sided(c["improved"], c["improved"] + c["worsened"]),
                       "mean_score_diff": mean, "ci_low": lo, "ci_high": hi,
                       **{f"{k}_onlyA_onlyB_p": discordant(ps, k) for k in ("missed_scam", "unsafe_outcome", "false_alarm")}}

    # ---- noise check: condition A against the identical configuration in the 1 Nov benchmark
    noise = None
    if reference and (reference / "records.jsonl").exists():
        ref = {r["id"]: r for r in (json.loads(l) for l in (reference / "records.jsonl").read_text(encoding="utf-8").splitlines() if l.strip())
               if r.get("condition") == "secondlook" and not r.get("error")}
        common = [i for i in both if i in ref]
        flips = [i for i in common if ref[i]["tier"] != A[i]["tier"]]
        score_flips = [i for i in common if outcome_score(ref[i]["label"], ref[i]["tier"], ref[i]["risky"])
                       != outcome_score(A[i]["label"], A[i]["tier"], A[i]["risky"])]
        sc = lambda r: outcome_score(r["label"], r["tier"], r["risky"])
        noise = {"reference": f"runtime/results/{reference.name}", "common": len(common), "tier_flips": flips,
                 "score_flips": score_flips,
                 "score_up_in_A": [i for i in score_flips if sc(A[i]) > sc(ref[i])],
                 "score_down_in_A": [i for i in score_flips if sc(A[i]) < sc(ref[i])],
                 "score_flips_where_asking_differed": [i for i in score_flips
                                                       if (A[i]["n_questions"] > 0) != (ref[i]["n_questions"] > 0)],
                 "ref_messages_asked": sum(ref[i]["n_questions"] > 0 for i in common),
                 "A_messages_asked": sum(A[i]["n_questions"] > 0 for i in common),
                 "ref_metrics": metrics([ref[i] for i in common])}

    # ---- failure-analysis candidates (facts only; interpretation is written by a person)
    def case(p, why):
        a, b = A[p["id"]], B[p["id"]]
        return {"why": why, "id": p["id"], "label": p["label"], "category": p["category"],
                "asked_in_A": a["n_questions"] > 0, "A_questions": [f"{q['question']} -> {q['answer']}" for q in a["questions"]],
                "A_verdict": a["tier"], "A_raw": a["raw_tier"], "B_verdict": b["tier"], "B_raw": b["raw_tier"],
                "A_adjustments": a["adjustments"], "B_adjustments": b["adjustments"],
                "A_summary": a["summary"], "B_summary": b["summary"]}
    candidates = []
    candidates += [case(p, "1. clarification corrected the verdict") for p in paired
                   if p["change_with_clarification"] == "improved" and p["A_asked"]]
    candidates += [case(p, "2. did not ask although context decides the verdict") for p in paired
                   if p["category"] in ("context_dependent", "context_fits_scam") and not p["A_asked"] and p["A_score"] < 1]
    candidates += [case(p, "3. asking made the verdict worse") for p in paired
                   if p["change_with_clarification"] == "worsened" and p["A_asked"]]
    candidates += [case(p, "4. code rule prevented unsafe reassurance") for p in paired
                   if p["label"] == "scam" and ("looks_fine" in (p["A_raw_tier"], p["B_raw_tier"]))
                   and "looks_fine" not in (p["A_tier"], p["B_tier"])]
    wtext(out / "failure_candidates.json", json.dumps(candidates, indent=2, ensure_ascii=False))

    # ---- machine-readable bundle
    wtext(out / "analysis.json", json.dumps({"run_info": info, "matched_messages": len(both),
                                                   "errors": errors, "summary": summary, "paired": paired,
                                                   "stats": stats, "noise_check": noise}, indent=2, ensure_ascii=False))
    write_report(out, info, mock, both, errors, summary, paired, stats, noise, candidates)


def write_report(out, info, mock, both, errors, summary, paired, stats, noise, candidates):
    get = lambda subset, c: next(s for s in summary if s["subset"] == subset and s["condition"] == c)
    diff = "".join(difflib.unified_diff(SECONDLOOK_INSTRUCTIONS.splitlines(True), SECONDLOOK_NO_ASK_INSTRUCTIONS.splitlines(True),
                                        "SECONDLOOK_INSTRUCTIONS (A)", "SECONDLOOK_NO_ASK_INSTRUCTIONS (B)", n=0))
    L = ["# Ablation: contextual clarification (Idea 1)\n"]
    if mock:
        L.append("> **MOCK MODE.** These numbers come from the rule-based stand-in model and only test the pipeline. "
                 "They are NOT results and must not be reported.\n")
    L += [f"Model: `{info.get('model')}` via {info.get('provider')} · temperature {info.get('temperature')} · "
          f"reasoning effort `{info.get('reasoning_effort')}` · "
          + (f"seed {info.get('seed')} (accepted: {info.get('seed_supported')}; best effort, not a guarantee of identical outputs)  "
             if info.get('seed') is not None else
             "no seed, as in the main benchmark (the provider does not guarantee deterministic outputs either way)  "),
          f"Started {info.get('started')} · finished {info.get('finished', 'not finished')}  ",
          f"Messages with a valid result in **both** conditions: **{len(both)} of 40**. Errors recorded: {len(errors)}.\n",
          "## Research question\n",
          "Does allowing SecondLook to ask contextual clarification questions reduce missed scams and unsafe reassurance, "
          "compared with the same system without clarification?\n",
          "## Conditions\n",
          "- **A: SecondLook (clarification).** The full system as in the main benchmark: `ask_user` tool, at most 2 questions, "
          "answers from a simulated person who reads the message's context card (same mapping as the main benchmark).\n",
          "- **B: SecondLook without clarification.** Identical except: the `ask_user` tool is not offered and a stray call is "
          "refused by the application; the question limit is 0; no simulated person is attached (any attempt to obtain an "
          "answer fails the check); step 4 of the instructions says the model cannot ask.\n",
          "- **Identical in both:** model, provider, temperature, reasoning effort, sampling settings (no seed unless --seed is given), advisory corpus and search, "
          "`recall_context` (memory off in both, so it always returns nothing), tiers, code-enforced rules, evidence checks, "
          "dataset (40 messages, same IDs, labels and order), date given to the model, and scoring.\n",
          "- Conditions run back to back for each message, alternating A-B and B-A.\n",
          "### Exact instruction difference\n", "```diff\n" + diff + "```\n",
          "## Metric definitions\n",
          "- **Missed scam:** a scam (label `scam`) whose final verdict is `looks_fine` or `verify_safe_route`, i.e. not flagged as a "
          "likely scam or as unclear. Denominator: scams.\n",
          "- **Unsafe outcome:** a scam whose final verdict is `looks_fine`, the most reassuring tier (this counts the verdict, not what a person would do). Denominator: scams.\n",
          "- **False alarm:** a genuine message (label `legit`) whose final verdict is `likely_scam` or `cant_tell`. Denominator: genuine messages.\n",
          "- **Friction:** a genuine message that requests nothing risky but is not called `looks_fine`.\n",
          "- **Questions per message:** clarification questions asked, divided by messages.\n",
          "- **Outcome score:** the main benchmark's per-message score (1 best, 0 worst; see `eval/metrics.py`). Used for the paired comparison: "
          "a message is *improved* if A's score is higher than B's, *worsened* if lower, *unchanged* if equal.\n",
          "- **Tokens per check:** total tokens reported by the provider for the check, averaged.\n",
          "All metrics use the final verdict, after the code-enforced rules, exactly as in the main benchmark.\n",
          "## Results\n"]
    hdr = ["Condition", "Missed scams", "Unsafe outcomes", "False alarms", "Friction", "Questions / msg",
           "Msgs with a question", "Mean outcome score", "Tokens / check"]
    for subset, title in (("all", "All matched messages"), ("context_dependent", "Context-dependent subset (identical-text pairs)")):
        rows_ = []
        for c in CONDITIONS:
            s = get(subset, c)
            rows_.append([LABEL[c], f"{s['missed_scams']}/{s['scams']}", f"{s['unsafe_outcomes']}/{s['scams']}",
                          f"{s['false_alarms']}/{s['genuine']}", f"{s['friction']}/{s['genuine']}", s["questions_per_msg"],
                          f"{s['messages_with_a_question']}/{s['messages']}", s["mean_outcome_score"], s["mean_tokens_per_check"]])
        L += [f"### {title}\n", table(hdr, rows_)]
    rows_ = []
    for subset in ("context_fits_scam", "clear_scam", "clear_legit"):
        for c in CONDITIONS:
            s = get(subset, c)
            if s["messages"]:
                rows_.append([subset, LABEL[c][:1], f"{s['missed_scams']}/{s['scams']}", f"{s['unsafe_outcomes']}/{s['scams']}",
                              f"{s['false_alarms']}/{s['genuine']}", s["questions_per_msg"], s["mean_outcome_score"]])
    L += ["### Other categories\n", table(["Category", "Cond.", "Missed", "Unsafe", "False alarms", "Q/msg", "Score"], rows_)]

    L += ["## Paired per-message comparison\n"]
    for name in ("all", "context_dependent"):
        st = stats[name]
        L += [f"**{name}:** improved with clarification {st['improved']} ({st['improved_with_question']} with a question asked in A), "
              f"worsened {st['worsened']} ({st['worsened_with_question']} with a question asked in A), unchanged {st['unchanged']}. "
              f"Exact sign test on the {st['improved'] + st['worsened']} changed messages: two-sided p {fmt_p(st['sign_test_p'])}. "
              f"Mean outcome-score difference (A - B) {st['mean_score_diff']:+.3f}, paired bootstrap 95% interval "
              f"[{st['ci_low']:+.3f}, {st['ci_high']:+.3f}].  "]
        for k, nm in (("missed_scam", "missed scams"), ("unsafe_outcome", "unsafe outcomes"), ("false_alarm", "false alarms")):
            oa, ob, p = st[f"{k}_onlyA_onlyB_p"]
            L.append(f"- {nm}: only in A {oa}, only in B {ob} (exact McNemar p {fmt_p(p)})")
        L.append("")
    L += ["With 40 messages and few changed verdicts these tests have little power. A non-significant result means the data "
          "cannot distinguish the conditions, not that they are equal.\n",
          table(["ID", "Label", "Category", "A verdict", "B verdict", "A asked", "Change"],
                [[p["id"], p["label"], p["category"], p["A_tier"], p["B_tier"], p["A_questions"] or "-", p["change_with_clarification"]]
                 for p in paired])]
    if noise:
        rm = noise["ref_metrics"]
        L += ["## Run-to-run noise check\n",
              f"Condition A uses the same configuration as SecondLook in the 1 Nov benchmark (`{noise['reference']}`)"
              + (f", except that this run sent seed {info.get('seed')} and that run sent none. " if info.get("seed") is not None else ". ") +
              f"On the {noise['common']} shared messages, the final verdict differed on **{len(noise['tier_flips'])}** "
              f"({', '.join(noise['tier_flips']) or 'none'}) and the outcome score on **{len(noise['score_flips'])}**. "
              f"Of the score changes, {len(noise['score_up_in_A'])} were better in this run and {len(noise['score_down_in_A'])} worse, and in "
              f"{len(noise['score_flips_where_asking_differed'])} of them the model asked a question in one run but not the other "
              f"({noise['ref_messages_asked']} messages with a question then, {noise['A_messages_asked']} now). "
              f"That run had {rm['missed_scams']}/{rm['scams']} missed scams, {rm['unsafe_outcomes']}/{rm['scams']} unsafe outcomes and "
              f"{rm['false_alarms']}/{rm['genuine']} false alarms on these messages. Differences between A and B that are no larger than "
              "this run-to-run variation should not be interpreted.\n"]
    L += ["## Failure-analysis candidates\n",
          f"{len(candidates)} candidates, listed by the four priorities in `failure_candidates.json` (facts only). "
          "The explanations for the chosen cases are written after reading each transcript.\n"]
    for cnd in candidates[:12]:
        L.append(f"- **{cnd['id']}** ({cnd['label']}, {cnd['category']}) - {cnd['why']}: A {cnd['A_verdict']} "
                 f"(asked: {'; '.join(cnd['A_questions']) or 'no'}), B {cnd['B_verdict']}"
                 f"{' (raw ' + cnd['B_raw'] + ')' if cnd['B_raw'] != cnd['B_verdict'] else ''}")
    if errors:
        L += ["\n## Errors (not counted as verdicts)\n"] + [f"- {e['condition']} {e['id']}: {e['error'][:200]}" for e in errors]
    L += ["\n## Limitations\n",
          "- One run per condition on 40 synthetic messages; the simulated person always answers truthfully.\n",
          "- The provider does not guarantee deterministic sampling, even with a seed.\n",
          "- Condition B's instructions differ in one step, which is the minimum needed so the prompt does not refer to a tool that does not exist.\n",
          "- The context-dependent pairs are built so that only the person's context decides, which favours asking by design.\n",
          "\n## Files and reproduction\n",
          "- `results.jsonl`: one line per message and condition, with verdicts, questions and answers, tokens and errors.\n",
          "- `summary.csv`: all metrics, per condition, for all messages and per category.\n",
          "- `paired_comparison.csv`: per-message A vs B with improved / worsened / unchanged.\n",
          "- `analysis.json`: everything above plus statistics and the noise check. `failure_candidates.json`: cases for the failure analysis.\n",
          "- Code: `eval/ablation_clarification.py` (new), `tests/test_ablation.py` (new); `secondlook/agent.py` and `secondlook/prompts.py` "
          "(clarification switch, default on, so the app and the main benchmark are unchanged).\n",
          "- Reproduce: `python -m eval.ablation_clarification`, then `--resume <folder>` if the daily limit stops it, or "
          "`--analyse <folder>` to rebuild these outputs.\n"]
    wtext(out / "report.md", "\n".join(L))


async def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # never crash on printing an unusual character
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", help="ablation folder to complete")
    ap.add_argument("--analyse", help="ablation folder to analyse without running anything")
    ap.add_argument("--ids", nargs="+", help="only these message IDs (for a smoke test)")
    ap.add_argument("--seed", type=int, default=None,
                    help="optional best-effort seed. Off by default so condition A matches the main benchmark exactly")
    ap.add_argument("--reference", default=str(DEFAULT_REFERENCE), help="main-benchmark folder for the noise check")
    args = ap.parse_args()
    reference = pathlib.Path(args.reference) if args.reference else None
    if args.analyse:
        out = pathlib.Path(args.analyse)
        analyse(out, reference)
        print((out / "report.md").read_text(encoding="utf-8"))
        return
    msgs = json.loads((DATA / "messages.json").read_text(encoding="utf-8"))
    if args.ids:
        msgs = [m for m in msgs if m["id"] in args.ids]
    if args.resume:
        out = pathlib.Path(args.resume)
        info = json.loads((out / "run_info.json").read_text(encoding="utf-8"))
        if info.get("mock") != use_mock() or info.get("model") != MODEL:
            raise SystemExit(f"Refusing to resume: this folder was run with model={info.get('model')} mock={info.get('mock')}, "
                             f"but the current settings are model={MODEL} mock={use_mock()}.")
        seed = info.get("seed")
    else:
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        out = OUT_ROOT / (f"MOCK-{stamp}" if use_mock() else stamp)
        out.mkdir(parents=True)
        seed = args.seed
        wtext(out / "run_info.json", json.dumps({
            "model": MODEL, "provider": PROVIDER_LABEL, "temperature": TEMPERATURE, "reasoning_effort": REASONING_EFFORT,
            "seed": seed, "mock": use_mock(), "max_questions_A": agent.MAX_QUESTIONS, "max_questions_B": 0,
            "memory": "off in both conditions", "message_ids": [m["id"] for m in msgs],
            "started": f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}"}, indent=2))
    if use_mock():
        print("MOCK MODE: rule-based stand-in model. This only tests the pipeline; the numbers are NOT results.")
    finished = await run(out, msgs, seed)
    analyse(out, reference)
    print("\n" + (out / "report.md").read_text(encoding="utf-8"))
    print(f"\nSaved to {out}")
    if not finished:
        print(f"\nNOT FINISHED. Resume with:\n    python -m eval.ablation_clarification --resume \"{out}\"")


if __name__ == "__main__":
    asyncio.run(main())
