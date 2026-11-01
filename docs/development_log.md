# Development log

This records the main changes made after the proposal feedback and after the first live runs. It explains why some parts of the code look the way they do.

## 1. Feedback: "How would the agent decide when to forget? Does the user need to specify it every time?"

SecondLook now forgets on its own, in layers, and the user taps at most once.

| Layer | Before | After |
|---|---|---|
| Lifetime | The model guessed `days_valid` (1–14) | The **app** sets it per fact type: parcel 5 days, selling an item 14, job applications 30, bank account 90. The user can change it with one tap when saving. |
| Ending event | none | A **genuine** message that ends the situation ("has been delivered", "marked as sold") offers **"Forget it?"**. A scam verdict can never trigger forgetting. |
| Re-check before relaxing caution | none | A remembered fact older than **48 h** is not trusted silently when the message asks for money, a link or a code. The app pauses with "Are you still expecting a parcel delivery?". Yes renews the fact, No forgets it. Enforced in code (`recall_context`), not by the prompt. |
| Contradiction | Replaced only when a new suggestion was saved | Any answer that conflicts with memory forgets it immediately |
| What can be stored | Any key the model invented | Only 4 lasting situations. One-off facts (an OTP request, a payment) are never stored. Invalid entries are dropped on load. |

`eval/memory_eval.py` compares four modes (off, permanent, fixed expiry, adaptive) on a 15-day scenario in which one parcel arrives early with a "delivered" message, a second arrives silently, and fake cash-on-delivery texts arrive while a 5-day memory is still unexpired.

Files: `secondlook/memory.py`, `secondlook/agent.py` (`recall_context`, `CheckSession.answer`), `secondlook/schemas.py`, `app.py`, `data/memory_scenario.json`, `eval/memory_eval.py`, `tests/test_forgetting.py`, `tests/test_memory.py`.

## 2. Feedback: "Consider focusing on a few common types"

The data and labels did not change. Each message was tagged with a scam type (`topic` in `data/messages.json`: `delivery_ecommerce`, `phishing`, `job`, `out_of_scope`, `everyday`). The evaluation report adds a focus-scope table and a per-type breakdown. 17 of the 20 scam messages fall in the three focus types, and the other 3 are reported separately as an out-of-scope probe. The app states its scope and shows a note when a message falls outside it.

## 3. Moving from the OpenAI Agents SDK to Groq

The proposal planned the OpenAI Agents SDK. The project moved to Groq (`openai/gpt-oss-120b`) for access and cost, using a tool-calling loop written for this project. Fixes made during the move:

| Problem | Effect | Fix |
|---|---|---|
| Baseline answers `{"is_scam": …}` fell through to a fallback | Baselines always answered "can't tell" | Baselines are parsed properly and their prompts require that JSON |
| Non-JSON or fenced replies became "can't tell" | Silent wrong verdicts | Accepts ```json fences, tries one repair, then records a visible error |
| Tool results were sent as user messages | The model could not match results to calls | Standard `assistant.tool_calls` and `role: tool` messages |
| Tool parameters had no allowed values | The model invented context keys | `message_type` and `context_key` restricted to fixed lists |
| Temperature 0.7 | Noisy evaluation runs | Default 0.2 |

## 4. Fixes after the first live runs (31 Oct)

The first two live runs (`runtime/results/20261031-190901` and `20261031-191411`) had 59 and 31 errors out of 120 checks.

| Cause | Fix |
|---|---|
| `gpt-oss-120b` on Groq sometimes sends its final answer as a call to a non-existent tool named `json` | The answer is recovered from the error and counted as "recovered" in the report |
| Misspelled tool names and malformed tool arguments | One correction message, then a retry |
| Per-minute rate limit (8,000 tokens) | Waits the time Groq asks for, then retries. One check at a time by default. |
| Per-day limit (200,000 tokens) | Stops cleanly and prints a `--resume` command. `reasoning_effort=low` and shorter advisory results reduce tokens per check. |
| Conditions compared on different message subsets | Reports use only messages that every condition answered |
| Memory scenario bug (the "delivered" day said "not expecting", couriers did not match) | Scenario corrected |
| The agent asked "did you make this payment?" but the OTP card only answered "did you request the code?" | For the two pairs where these questions mean the same thing, the card answers both. Labels unchanged. |
| The agent did not ask on a Singpass login alert or a "new number" message | One general prompt rule: account-activity notifications are genuine only if the person did the action, so ask. This is the only prompt revision made after a pilot on the benchmark messages. |

## 5. Clarification ablation (1 Nov)

`eval/ablation_clarification.py` runs the full system with and without clarification. A `clarification` switch in `secondlook/agent.py` (on by default, so the app and the main benchmark are unchanged) removes the `ask_user` tool, sets the question limit to 0 and swaps one instruction step (`SECONDLOOK_NO_ASK_INSTRUCTIONS` in `secondlook/prompts.py`). All files are read and written as UTF-8 so that runs on Windows do not fail on characters such as a non-breaking hyphen.
