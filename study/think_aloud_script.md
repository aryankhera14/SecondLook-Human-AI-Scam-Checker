# Facilitator script: SecondLook think-aloud study

**Time:** ~30 min per participant · **Participants:** 2–3 · **Setup:** laptop running `streamlit run app.py` in live mode, Study mode page.

## 1. Before you start (3 min)
- Read the consent form together; get a signed copy.
- Pick the order. Alternate between participants: P1 = "Set A alone, then Set B with SecondLook", P2 = the other order, P3 = like P1.
- Read the **participant card** shown at the top of Study mode aloud. They should answer any SecondLook questions as that person.

## 2. Instructions to read aloud
> "You'll see 8 messages. For each one, decide what you would really do. For the first four you're on your own; for the last four an assistant called SecondLook gives its view first. Please say what you're thinking as you go: what you notice, what you'd check, what you're unsure about. There are no right answers I'm looking for; I'm testing the tool, not you."

## 3. During the session
- Neutral prompt if they go quiet: **"What's on your mind right now?"**
- Never lead: don't say "look at the link" or "is that right?"
- Note on paper, per message: what they looked at first, whether they read the evidence, any doubts about the verdict, anything confusing.
- The app logs decision, confidence and time to `runtime/study_log.csv`.

## 4. Debrief (5 min)
- "Which AI verdicts did you trust, and why?"
- "Did the questions it asked make sense?"
- Reveal the planted wrong verdict (CD06b in set A, CD04b in set B) and ask: "Did anything about that one feel off?"

## 5. What to analyse (Week 2 appropriate reliance)
For each with-SecondLook message, classify the decision:

| AI verdict | Participant follows it | Participant overrides it |
|---|---|---|
| Correct | correct reliance | under-reliance |
| Wrong (planted) | **over-reliance** | correct self-reliance |

Also compare decisions **alone vs with SecondLook**: unsafe decisions ("act on it as the message asks") on scam messages, and time per message.
