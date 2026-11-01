# Ablation: contextual clarification (Idea 1)

Model: `openai/gpt-oss-120b` via Groq · temperature 0.2 · reasoning effort `low` · seed 619 (accepted: accepted by the API (no error); best effort, not a guarantee of identical outputs)  
Started 2026-11-01 19:47:23 · finished 2026-11-01 20:05:39  
Messages with a valid result in **both** conditions: **40 of 40**. Errors recorded: 0.

## Research question

Does allowing SecondLook to ask contextual clarification questions reduce missed scams and unsafe reassurance, compared with the same system without clarification?

## Conditions

- **A: SecondLook (clarification).** The full system as in the main benchmark: `ask_user` tool, at most 2 questions, answers from a simulated person who reads the message's context card (same mapping as the main benchmark).

- **B: SecondLook without clarification.** Identical except: the `ask_user` tool is not offered and a stray call is refused by the application; the question limit is 0; no simulated person is attached (any attempt to obtain an answer fails the check); step 4 of the instructions says the model cannot ask.

- **Identical in both:** model, provider, temperature, reasoning effort, sampling settings (no seed unless --seed is given), advisory corpus and search, `recall_context` (memory off in both, so it always returns nothing), tiers, code-enforced rules, evidence checks, dataset (40 messages, same IDs, labels and order), date given to the model, and scoring.

- Conditions run back to back for each message, alternating A-B and B-A.

### Exact instruction difference

```diff
--- SECONDLOOK_INSTRUCTIONS (A)
+++ SECONDLOOK_NO_ASK_INSTRUCTIONS (B)
@@ -12,7 +12,4 @@
-   applied). If it would, and recalled context does not already answer it, call ask_user with ONE
-   yes/no question, the matching context_key, and options ["Yes", "No", "Not sure"].
-   Account-activity notifications - a login alert, a one-time code, a payment or transfer alert, or a
-   "this is my new number" message - are genuine only if the person did that action or knows the sender,
-   so ask about them unless red flags already decide the verdict.
-   Do NOT ask when red flags already make it a likely scam, or when the answer would not change the verdict.
-   Never ask more than needed.
+   applied). In this version you cannot ask the person anything: there is no ask_user tool and no answers
+   will come. Account-activity notifications - a login alert, a one-time code, a payment or transfer alert, or a
+   "this is my new number" message - are genuine only if the person did that action or knows the sender.
+   Give your best verdict from the message, recalled context and the advisories alone.
```

## Metric definitions

- **Missed scam:** a scam (label `scam`) whose final verdict is `looks_fine` or `verify_safe_route`, i.e. not flagged as a likely scam or as unclear. Denominator: scams.

- **Unsafe outcome:** a scam whose final verdict is `looks_fine`, so the person would act through the message. Denominator: scams.

- **False alarm:** a genuine message (label `legit`) whose final verdict is `likely_scam` or `cant_tell`. Denominator: genuine messages.

- **Friction:** a genuine message that requests nothing risky but is not called `looks_fine`.

- **Questions per message:** clarification questions asked, divided by messages.

- **Outcome score:** the main benchmark's per-message score (1 best, 0 worst; see `eval/metrics.py`). Used for the paired comparison: a message is *improved* if A's score is higher than B's, *worsened* if lower, *unchanged* if equal.

- **Tokens per check:** total tokens reported by the provider for the check, averaged.

All metrics use the final verdict, after the code-enforced rules, exactly as in the main benchmark.

## Results

### All matched messages

| Condition | Missed scams | Unsafe outcomes | False alarms | Friction | Questions / msg | Msgs with a question | Mean outcome score | Tokens / check |
|---|---|---|---|---|---|---|---|---|
| A: SecondLook (clarification) | 1/20 | 1/20 | 2/20 | 0/20 | 0.35 | 14/40 | 0.925 | 4211 |
| B: SecondLook without clarification | 8/20 | 1/20 | 2/20 | 1/20 | 0.0 | 0/40 | 0.85 | 3395 |

### Context-dependent subset (identical-text pairs)

| Condition | Missed scams | Unsafe outcomes | False alarms | Friction | Questions / msg | Msgs with a question | Mean outcome score | Tokens / check |
|---|---|---|---|---|---|---|---|---|
| A: SecondLook (clarification) | 1/8 | 1/8 | 0/8 | 0/8 | 0.62 | 10/16 | 0.938 | 4896 |
| B: SecondLook without clarification | 8/8 | 1/8 | 0/8 | 0/8 | 0.0 | 0/16 | 0.719 | 3587 |

### Other categories

| Category | Cond. | Missed | Unsafe | False alarms | Q/msg | Score |
|---|---|---|---|---|---|---|
| context_fits_scam | A | 0/6 | 0/6 | 0/0 | 0.17 | 1.0 |
| context_fits_scam | B | 0/6 | 0/6 | 0/0 | 0.0 | 1.0 |
| clear_scam | A | 0/6 | 0/6 | 0/0 | 0.17 | 1.0 |
| clear_scam | B | 0/6 | 0/6 | 0/0 | 0.0 | 1.0 |
| clear_legit | A | 0/0 | 0/0 | 2/12 | 0.17 | 0.833 |
| clear_legit | B | 0/0 | 0/0 | 2/12 | 0.0 | 0.875 |

## Paired per-message comparison

**all:** improved with clarification 9 (6 with a question asked in A), worsened 3 (2 with a question asked in A), unchanged 28. Exact sign test on the 12 changed messages: two-sided p = 0.146. Mean outcome-score difference (A - B) +0.075, paired bootstrap 95% interval [-0.044, +0.188].  
- missed scams: only in A 0, only in B 7 (exact McNemar p = 0.016)
- unsafe outcomes: only in A 1, only in B 1 (exact McNemar p = 1.000)
- false alarms: only in A 2, only in B 2 (exact McNemar p = 1.000)

**context_dependent:** improved with clarification 7 (6 with a question asked in A), worsened 1 (0 with a question asked in A), unchanged 8. Exact sign test on the 8 changed messages: two-sided p = 0.070. Mean outcome-score difference (A - B) +0.219, paired bootstrap 95% interval [+0.062, +0.406].  
- missed scams: only in A 0, only in B 7 (exact McNemar p = 0.016)
- unsafe outcomes: only in A 1, only in B 1 (exact McNemar p = 1.000)
- false alarms: only in A 0, only in B 0 (exact McNemar p = 1.000)

With 40 messages and few changed verdicts these tests have little power. A non-significant result means the data cannot distinguish the conditions, not that they are equal.

| ID | Label | Category | A verdict | B verdict | A asked | Change |
|---|---|---|---|---|---|---|
| CD01a | legit | context_dependent | looks_fine | verify_safe_route | - | unchanged |
| CD01b | scam | context_dependent | likely_scam | verify_safe_route | initiated_payment_or_refund=No | improved |
| CD02a | legit | context_dependent | verify_safe_route | verify_safe_route | - | unchanged |
| CD02b | scam | context_dependent | likely_scam | verify_safe_route | requested_otp_or_login=No | improved |
| CD03a | legit | context_dependent | looks_fine | verify_safe_route | requested_otp_or_login=Yes | unchanged |
| CD03b | scam | context_dependent | likely_scam | verify_safe_route | requested_otp_or_login=No | improved |
| CD04a | legit | context_dependent | looks_fine | verify_safe_route | - | unchanged |
| CD04b | scam | context_dependent | looks_fine | verify_safe_route | - | worsened |
| CD05a | legit | context_dependent | verify_safe_route | verify_safe_route | applied_for_job=Yes | unchanged |
| CD05b | scam | context_dependent | likely_scam | verify_safe_route | applied_for_job=No | improved |
| CD06a | legit | context_dependent | verify_safe_route | verify_safe_route | expecting_delivery=Yes | unchanged |
| CD06b | scam | context_dependent | likely_scam | verify_safe_route | - | improved |
| CD07a | legit | context_dependent | verify_safe_route | verify_safe_route | initiated_payment_or_refund=Yes | unchanged |
| CD07b | scam | context_dependent | likely_scam | verify_safe_route | initiated_payment_or_refund=No | improved |
| CD08a | legit | context_dependent | looks_fine | looks_fine | - | unchanged |
| CD08b | scam | context_dependent | likely_scam | looks_fine | knows_sender_personally=No | improved |
| CF01 | scam | context_fits_scam | likely_scam | likely_scam | - | unchanged |
| CF02 | scam | context_fits_scam | likely_scam | likely_scam | - | unchanged |
| CF03 | scam | context_fits_scam | likely_scam | likely_scam | - | unchanged |
| CF04 | scam | context_fits_scam | likely_scam | likely_scam | - | unchanged |
| CF05 | scam | context_fits_scam | likely_scam | likely_scam | - | unchanged |
| CF06 | scam | context_fits_scam | likely_scam | likely_scam | requested_otp_or_login=Yes | unchanged |
| S01 | scam | clear_scam | likely_scam | likely_scam | - | unchanged |
| S02 | scam | clear_scam | likely_scam | likely_scam | - | unchanged |
| S03 | scam | clear_scam | likely_scam | likely_scam | requested_otp_or_login=Not sure | unchanged |
| S04 | scam | clear_scam | likely_scam | likely_scam | - | unchanged |
| S05 | scam | clear_scam | likely_scam | likely_scam | - | unchanged |
| S06 | scam | clear_scam | likely_scam | likely_scam | - | unchanged |
| L01 | legit | clear_legit | verify_safe_route | cant_tell | - | improved |
| L02 | legit | clear_legit | looks_fine | looks_fine | - | unchanged |
| L03 | legit | clear_legit | looks_fine | looks_fine | - | unchanged |
| L04 | legit | clear_legit | looks_fine | looks_fine | - | unchanged |
| L05 | legit | clear_legit | looks_fine | verify_safe_route | - | unchanged |
| L06 | legit | clear_legit | looks_fine | cant_tell | - | improved |
| L07 | legit | clear_legit | likely_scam | verify_safe_route | has_account_with_named_org=Not sure | worsened |
| L08 | legit | clear_legit | likely_scam | verify_safe_route | expecting_delivery=Not sure | worsened |
| L09 | legit | clear_legit | looks_fine | looks_fine | - | unchanged |
| L10 | legit | clear_legit | looks_fine | looks_fine | - | unchanged |
| L11 | legit | clear_legit | looks_fine | looks_fine | - | unchanged |
| L12 | legit | clear_legit | verify_safe_route | verify_safe_route | - | unchanged |

## Run-to-run noise check

Condition A uses the same configuration as SecondLook in the 1 Nov benchmark (`runtime/results/20261101-005051`), except that this run sent seed 619 and that run sent none. On the 40 shared messages, the final verdict differed on **10** (CD01a, CD02a, CD02b, CD03b, CD04b, CD05b, CD07a, CD08b, CF01, L08) and the outcome score on **8**. Of the score changes, 6 were better in this run and 2 worse, and in 8 of them the model asked a question in one run but not the other (12 messages with a question then, 14 now). That run had 5/20 missed scams, 3/20 unsafe outcomes and 2/20 false alarms on these messages. Differences between A and B that are no larger than this run-to-run variation should not be interpreted.

## Failure-analysis candidates

9 candidates, listed by the four priorities in `failure_candidates.json` (facts only). The explanations for the chosen cases are written after reading each transcript.

- **CD01b** (scam, context_dependent) - 1. clarification corrected the verdict: A likely_scam (asked: Did you recently make a SGD 1,240.00 card payment to Shopee SG? -> No), B verify_safe_route
- **CD02b** (scam, context_dependent) - 1. clarification corrected the verdict: A likely_scam (asked: Did you recently try to log in to Telegram or request a verification code? -> No), B verify_safe_route
- **CD03b** (scam, context_dependent) - 1. clarification corrected the verdict: A likely_scam (asked: Did you log in to Singpass on a new device at the time mentioned? -> No), B verify_safe_route
- **CD05b** (scam, context_dependent) - 1. clarification corrected the verdict: A likely_scam (asked: Did you apply for a Part-time Data Entry Assistant role with Kelly Services? -> No), B verify_safe_route
- **CD07b** (scam, context_dependent) - 1. clarification corrected the verdict: A likely_scam (asked: Did you transfer SGD 2,000.00 to TAN K M on 03 Oct at 21:14 using your OCBC account? -> No), B verify_safe_route
- **CD08b** (scam, context_dependent) - 1. clarification corrected the verdict: A likely_scam (asked: Do you know Wei Ming and were expecting a message about a new phone number from them? -> No), B looks_fine
- **CD04b** (scam, context_dependent) - 2. did not ask although context decides the verdict: A looks_fine (asked: no), B verify_safe_route
- **L07** (legit, clear_legit) - 3. asking made the verdict worse: A likely_scam (asked: Do you have a dental appointment scheduled with Smile Dental on 8 Oct? -> Not sure), B verify_safe_route
- **L08** (legit, clear_legit) - 3. asking made the verdict worse: A likely_scam (asked: Did you borrow the book "Thinking, Fast and Slow" from the National Library Board and have a loan due soon? -> Not sure), B verify_safe_route

## Limitations

- One run per condition on 40 synthetic messages; the simulated person always answers truthfully.

- The provider does not guarantee deterministic sampling, even with a seed.

- Condition B's instructions differ in one step, which is the minimum needed so the prompt does not refer to a tool that does not exist.

- The context-dependent pairs are built so that only the person's context decides, which favours asking by design.


## Files and reproduction

- `results.jsonl`: one line per message and condition, with verdicts, questions and answers, tokens and errors.

- `summary.csv`: all metrics, per condition, for all messages and per category.

- `paired_comparison.csv`: per-message A vs B with improved / worsened / unchanged.

- `analysis.json`: everything above plus statistics and the noise check. `failure_candidates.json`: cases for the failure analysis.

- Code: `eval/ablation_clarification.py` (new), `tests/test_ablation.py` (new); `secondlook/agent.py` and `secondlook/prompts.py` (clarification switch, default on, so the app and the main benchmark are unchanged).

- Reproduce: `python -m eval.ablation_clarification`, then `--resume <folder>` if the daily limit stops it, or `--analyse <folder>` to rebuild these outputs.
