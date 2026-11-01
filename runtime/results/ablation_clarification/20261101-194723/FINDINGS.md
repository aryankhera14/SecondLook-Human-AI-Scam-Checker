# Clarification ablation: findings

Run `runtime/results/ablation_clarification/20261101-194723`, 1 Nov 2026, 19:47 to 20:05. Model `openai/gpt-oss-120b` on Groq, temperature 0.2, low reasoning effort, seed 619 in both conditions (accepted by the API, best effort only). 80 checks, **0 errors**, all 40 messages valid in both conditions. In 7 checks the final answer arrived as a malformed tool call and was recovered, as in the main benchmark. Full tables, metric definitions and the exact instruction difference are in `report.md` in this folder.

## Method in brief

- **A, clarification:** the full SecondLook system, as in the main benchmark. It can ask up to two questions, which a simulated person answers from each message's context card.
- **B, no clarification:** the same system with the `ask_user` tool removed and a question limit of 0. No simulated person is attached, so an attempt to obtain an answer would fail the check (none occurred). Step 4 of the instructions says the model cannot ask.
- **Identical in both:** model, settings, seed, advisories, tiers, code rules, evidence checks, dataset, labels, scoring. Memory is off in both.
- The two conditions ran back to back on each message, alternating which went first.

## Results (raw counts)

| | A: clarification | B: no clarification |
|---|---|---|
| Missed scams (scam not called likely scam or can't tell) | **1/20** | **8/20** |
| Unsafe outcomes (scam called "looks fine") | 1/20 | 1/20 |
| False alarms (genuine called scam or can't tell) | 2/20 | 2/20 |
| Friction (harmless genuine not called fine) | 0/20 | 1/20 |
| Questions per message | 0.35 (14 of 40 messages) | 0 |
| Mean outcome score | 0.925 | 0.850 |
| Tokens per check | 4,211 | 3,395 |
| **Context-dependent subset (16):** missed / unsafe / false alarms | 1/8 · 1/8 · 0/8 | 8/8 · 1/8 · 0/8 |

**Paired comparison** (outcome score per message):
- All 40 messages: clarification improved 9 (6 of them after a question), worsened 3 (2 after a question), unchanged 28.
  - Sign test p = 0.146.
  - Mean score difference +0.075, 95% bootstrap interval [-0.044, +0.188].
- Context-dependent subset: improved 7, worsened 1.
  - Sign test p = 0.070.
  - Mean score difference +0.219, interval [+0.062, +0.406].
- Missed scams: 7 discordant pairs, all favouring A (exact McNemar p = 0.016).
- Unsafe outcomes: 1 vs 1 (p = 1.0).
- False alarms: 2 vs 2 (p = 1.0).

**Run-to-run noise.** Condition A was compared with SecondLook in the main benchmark, which used the same configuration except that it sent no seed.
- 10 of 40 verdicts and 8 of 40 outcome scores differed between the two runs: 6 better in this run, 2 worse.
- In all 8 score changes, the model asked a question in one run but not the other. The main benchmark asked on 12 messages, this run on 14.
- The missed-scam gap between A and B (7 to 0) goes in one direction, while the run-to-run changes went in both. But the two are similar in size, so this is one run, not a settled estimate.

## Findings

1. **Clarification mainly turns "verify the safe way" into "likely scam" on context-dependent scams.** Without an answer, the model sent 7 of the 8 context-dependent scams down the safe route instead of flagging them. With an answer, it flagged 7 of 8.
2. **Clarification did not reduce unsafe reassurance in this run.** Both conditions had one unsafe outcome. Without clarification, the model already chose the cautious "verify the safe way" tier itself (its raw verdict, before any code rule) on 7 of 8 context-dependent scams. So the tiered design, not asking, kept the system without clarification safe.
3. **Each condition's unsafe outcome came from a missing question.** B could not ask about a "new number" message (CD08b), and A did not ask about a fake Grab recruiter (CD04b).
4. **Asking caused both of A's false alarms.** Both were questions the simulated person could not answer ("Not sure"), which the model then treated as suspicion.
5. **Whether the model asks is unstable**, and it drives most of the run-to-run variation. The same configuration asked about CD04b in the main benchmark and caught it, but did not ask this time.
6. **Cost:** clarification used about 24% more tokens per check.

## Failure analysis (five cases)

| ID | Label | Asked in A? | A verdict | B verdict | Explanation |
|---|---|---|---|---|---|
| CD08b "new number" | scam | Yes: "Do you know Wei Ming…?" → No | likely_scam | **looks_fine** | **Clarification corrected an unsafe verdict.** The message requests nothing risky, so no code rule applies, and B's only unsafe outcome is here. A's question supplied the deciding fact. |
| CD01b DBS OTP | scam | Yes: "Did you make a SGD 1,240 payment to Shopee?" → No | likely_scam | verify_safe_route | **Typical correction.** B wrote that it "could be a phishing attempt" but could not decide, so it chose the safe route: safe, but the scam was not named. B also took the safe route on CD02b, CD03b, CD05b, CD06b and CD07b. A flagged all five, after a question in every case except CD06b. |
| CD04b Grab recruiter | scam | **No** | **looks_fine** | verify_safe_route | **Failed to ask despite missing decisive context.** A accepted the recruiter's claim. The risky-request detector found nothing ("Are you free for a call?"), so the code rule could not raise it. The same configuration asked here in the main benchmark and caught it. A's only unsafe outcome. |
| L07 dental reminder | legit | Yes: "Do you have an appointment…?" → Not sure | **likely_scam** | verify_safe_route | **Asking made it worse.** The context card has no relevant fact, so the simulated person said "Not sure", and the model read uncertainty as suspicion. L08 (library loan) is the same. A real person would probably know, so this is partly an artefact of the simulation. Either way, "Not sure" should keep the verdict cautious, not turn it into an accusation. |
| Code rules | – | – | – | – | **No case in this run where a code rule prevented unsafe reassurance on a scam.** All 5 rule changes (4 in A, 1 in B) raised genuine messages from "looks fine" to "verify the safe way". B's safety on context-dependent scams came from the model's own tier choice. CD04b shows the rule's gap: a scam that asks for nothing risky gets no protection from it. |

## Limitations

- One run per condition on 40 synthetic messages.
- The simulated person answers truthfully, and "Not sure" when the card has no matching fact.
- Run-to-run variation is about as large as the observed effects, so these numbers are indicative.
- The context-dependent pairs are built so that only context decides, which favours asking by design.
- Condition B changes one instruction step, which is the minimum needed so the prompt does not mention a missing tool.
- The seed was sent in both conditions. Groq treats it as best effort, so it does not make runs reproducible.

## Implications

- Clarification adds value only when the model actually asks, and that decision is the weak link.
- For context-dependent message types (one-time codes, account alerts, deliveries, recruiters, "new number" messages), the application, not the prompt, should decide to ask.
- A "Not sure" answer should lead to a cautious verdict, not an accusation.
- The risky-request detector should treat a request to reply, call back or schedule a call as risky.

## Files and reproduction

**Created**
- `eval/ablation_clarification.py`: runs both conditions, resumes after the daily limit, writes all outputs.
- `tests/test_ablation.py`: 12 tests. They check that condition B cannot call `ask_user` or reach the simulated person or context cards, that the defaults are unchanged, that the seed is handled correctly, that the statistics are right, and that results with unusual characters save as UTF-8.

**Modified**
- `secondlook/agent.py` and `secondlook/prompts.py`: a `clarification` switch (default on, so the app and main benchmark behave as before), the no-asking instruction variant, and an optional best-effort seed.
- `tests/test_resilience.py`: the optional OpenRouter test is skipped when the `openai` package is not installed.

**Outputs in this folder**
- `results.jsonl`: per message and condition.
- `summary.csv`: all metrics.
- `paired_comparison.csv`: improved, worsened or unchanged per message.
- `analysis.json`: statistics and the noise check.
- `failure_candidates.json`
- `report.md`: methodology and tables.
- `FINDINGS.md`: this file.

**Commands**
```
pytest -q                                                   # 63 passed, 1 skipped (64 if openai is installed)
python -m eval.ablation_clarification --seed 619            # this run used seed 619 (it was the default then)
python -m eval.ablation_clarification --resume <folder>     # finish a run stopped by the daily limit
python -m eval.ablation_clarification --analyse <folder>    # rebuild report.md and the CSVs from results.jsonl
```

## Evaluation subsection for the report (draft, 289 words)

**Ablation: does clarification help?** To isolate the effect of asking, we ran SecondLook on the 40-message benchmark with and without clarification. Both versions used the same model, settings, advisories, tiers and code rules, with memory turned off. The version without clarification had no ask_user tool, and one instruction step told it that the person could not be asked. The two versions ran back to back on each message.

Clarification reduced missed scams from 8 of 20 to 1 of 20, and all seven discordant scams favoured the clarifying version (exact McNemar p = 0.016). Without the person's answer, the model sent seven of the eight context-dependent scams down the safe route instead of flagging them. Unsafe outcomes did not change (1 of 20 in each version), and neither did false alarms (2 of 20 in each). The tiered design, not clarification, kept the version without questions from reassuring the person. Clarification cost about 24% more tokens per check.

The failures show where the remaining risk lies. Each version's single unsafe outcome was a scam on which no question was asked. The version without clarification could not ask about a "new number" message, and the full system chose not to ask about a fake recruiter. Asking also caused both of the full system's false alarms, when the simulated person could not answer and the model treated "Not sure" as suspicion. Between this run and the main benchmark, which used the same configuration apart from a fixed seed, 8 of 40 outcomes changed in both directions, and each change coincided with a difference in whether the model asked. Clarification improves verdicts when it is used, but the decision to ask is unreliable and should move from the prompt into the application.
