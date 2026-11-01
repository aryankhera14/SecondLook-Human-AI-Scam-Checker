# Screenshots

These screenshots should come from the running app with a live model (no yellow MOCK MODE banner), so that the verdicts shown are genuine model outputs. Save them in this folder with these names:

| File | What to show | How to get it |
|---|---|---|
| `1-submit.png` | Message submission | "Check a message" page with a message pasted, before pressing **Check message** |
| `2-question.png` | Contextual clarification | A context-dependent message, e.g. the Ninja Van cash-on-delivery text (`CD06b` in `data/messages.json`), showing the question card |
| `3-verdict.png` | Evidence-backed verdict | The verdict after answering, with highlighted red flags and the advisory quote visible |
| `4-next-step.png` | Safe next step | The "what to do next" part of a verdict, ideally one where the message's own link or number was replaced |
| `5-memory.png` | Memory consent or forgetting | The "Remember for" save card, or the "Forget it?" offer after a "has been delivered" message |

`python -m secondlook.demo_tools show | age N | reset` helps set up memory states for the last screenshot.
