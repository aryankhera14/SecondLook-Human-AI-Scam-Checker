"""SecondLook - Streamlit interface.   Run:  streamlit run app.py"""
import asyncio
import csv
import datetime as dt
import html
import json

import streamlit as st

from secondlook.agent import CheckSession, QuotaExhausted
from secondlook.config import DATA, MODEL, PROVIDER_LABEL, RUNTIME, use_mock
from secondlook.guardrails import check_red_flags
from secondlook.memory import MemoryStore
from secondlook.schemas import LIFETIME_CHOICES, MEMORY_LIFETIME_DAYS, TIER_LABELS

st.set_page_config(page_title="SecondLook", page_icon="🔎", layout="centered")

TIER_STYLE = {
    "looks_fine": ("#e8f5e9", "#1b5e20", "✓"),
    "verify_safe_route": ("#fff8e1", "#7a5600", "!"),
    "likely_scam": ("#ffebee", "#b71c1c", "✕"),
    "cant_tell": ("#eceff1", "#37474f", "?"),
}
st.markdown("""<style>
.verdict {border-radius:10px;padding:14px 18px;margin:6px 0 14px 0;}
.verdict h3 {margin:0 0 4px 0;font-size:1.25rem;}
.msgbox {background:#fafafa;border:1px solid #e0e0e0;border-radius:8px;padding:12px 14px;line-height:1.6;color:#111;}
.msgbox mark {background:#ffcdd2;padding:1px 2px;border-radius:3px;}
.next {background:#e3f2fd;border-radius:8px;padding:12px 14px;color:#0d2b45;}
.small {color:#666;font-size:0.85rem;}
.memcard {background:#f3e5f5;border-radius:8px;padding:10px 14px;margin:8px 0;color:#3b1d4a;}
</style>""", unsafe_allow_html=True)


def run(coro):
    """Run one step; turn provider errors (e.g. Groq 429 rate limits) into a friendly error step."""
    try:
        return asyncio.run(coro)
    except QuotaExhausted:
        return {"type": "error", "error": "The model provider's daily token limit has been reached. Wait for it to reset "
                                          "or upgrade the plan, then press Retry."}
    except Exception as e:
        status = getattr(e, "status_code", None)
        if status == 429:
            return {"type": "error", "error": "The model provider is rate-limiting requests right now. Wait a minute, then press Retry."}
        return {"type": "error", "error": f"{type(e).__name__}: {str(e)[:200]}"}


def memory() -> MemoryStore:
    if "memory" not in st.session_state:
        st.session_state.memory = MemoryStore(RUNTIME / "memory.json", mode="adaptive")
    return st.session_state.memory


def highlight(text: str, flags: list) -> str:
    spans = sorted({tuple(f["span"]) for f in flags if f.get("span")})
    flat = " ".join(text.split())  # spans are computed on whitespace-normalised text
    out, pos = [], 0
    for a, b in spans:
        if a < pos:
            continue
        out += [html.escape(flat[pos:a]), f"<mark>{html.escape(flat[a:b])}</mark>"]
        pos = b
    out.append(html.escape(flat[pos:]))
    return "".join(out)


def show_result(res: dict, text: str, allow_memory: bool = True):
    v = res["verdict"]
    bg, fg, icon = TIER_STYLE[v["tier"]]
    rule_notes = "".join(f"<div class='small' style='color:{fg};margin-top:6px'>Safety rule: {html.escape(n)}</div>"
                         for n in res["adjustments"] if n.startswith("Raised"))
    st.markdown(f"<div class='verdict' style='background:{bg};color:{fg}'><h3>{icon} {TIER_LABELS[v['tier']]}</h3>"
                f"{html.escape(v['summary'])}{rule_notes}</div>", unsafe_allow_html=True)
    if res.get("out_of_scope"):
        st.info("SecondLook is designed for delivery & e-commerce, bank/OTP/login phishing and job messages. "
                "This message is outside those types, so treat the verdict with extra care.")
    for ev in res.get("memory_events", []):
        st.markdown(f"<div class='memcard'>🧠 {html.escape(ev)}</div>", unsafe_allow_html=True)
    flags = [f for f in res["red_flags"] if f["phrase_verified"]]
    st.markdown(f"<div class='msgbox'>{highlight(text, flags)}</div>", unsafe_allow_html=True)
    if res["red_flags"]:
        st.markdown("**Why — evidence you can check**")
        for f in res["red_flags"]:
            mark = "" if f["phrase_verified"] else " _(phrase not found in the message — ignore)_"
            st.markdown(f"- **“{html.escape(f['phrase'])}”** — {html.escape(f['reason'])}{mark}")
            if f["quote_verified"]:
                st.markdown(f"  > {f['advisory_quote']}  \n  > — [{f['advisory_title']}]({f['source_url']})")
            else:
                st.markdown("  <span class='small'>(advisory quote could not be verified, so it is not shown)</span>",
                            unsafe_allow_html=True)
    st.markdown(f"<div class='next'><b>What to do next</b><br>{html.escape(v['safe_next_step'])}</div>",
                unsafe_allow_html=True)
    with st.expander("How this verdict was reached"):
        for q in res["questions"]:
            st.write(f"You were asked: “{q['question']}” → **{q.get('answer', '-')}**")
        for r in res["recalled"]:
            st.write(f"Remembered context used: “{r['fact']}”")
        for ev in res.get("memory_events", []):
            st.write(f"Memory: {ev}")
        for n in res["adjustments"]:
            st.write(f"Safety rule applied: {n}")
        if not (res["questions"] or res["recalled"] or res["adjustments"]):
            st.write("Judged from the message and official advisories only.")
        st.caption(f"Risky requests detected: {', '.join(v['risky_requests']) or 'none'} · tokens: {res['tokens']}")
    if allow_memory:
        forget_offers(res)
        suggestions = [s for s in v["memory_suggestions"] if s["context_key"] in MEMORY_LIFETIME_DAYS]
        if suggestions:
            st.markdown("**Remember this for next time?** SecondLook only saves what you approve, and forgets "
                        "it automatically: when it expires, when a message shows the situation has ended, or "
                        "when you tell it the fact is no longer true.")
        for i, s in enumerate(suggestions):
            key = f"mem_{id(res)}_{i}"
            if st.session_state.get(key + "_done"):
                st.caption(st.session_state[key + "_done"])
                continue
            default = MEMORY_LIFETIME_DAYS[s["context_key"]]
            st.markdown(f"<div class='memcard'>“{html.escape(s['fact'])}”</div>", unsafe_allow_html=True)
            days = st.radio("Remember for", LIFETIME_CHOICES, index=LIFETIME_CHOICES.index(default), horizontal=True,
                            format_func=lambda d: f"{d} day" + ("s" if d > 1 else "") + (" (suggested)" if d == default else ""),
                            key=key + "_days")
            c1, c2, _ = st.columns([1.2, 1.4, 4])
            if c1.button("Save", key=key + "_y", type="primary"):
                memory().add(s, dt.datetime.now(), days=days)
                st.session_state[key + "_done"] = f"Saved for {days} day(s): “{s['fact']}”"
                st.rerun()
            if c2.button("Don't save", key=key + "_n"):
                st.session_state[key + "_done"] = "Not saved."
                st.rerun()


def forget_offers(res: dict):
    """Event-based forgetting: one tap when a genuine message shows the situation has ended."""
    for offer in res.get("forget_offers", []):
        key = f"forget_{id(res)}_{offer['item_id']}"
        if st.session_state.get(key):
            st.caption(st.session_state[key])
            continue
        st.markdown(f"<div class='memcard'>🧠 {html.escape(offer['prompt'])}</div>", unsafe_allow_html=True)
        c1, c2, _ = st.columns([1.2, 1.4, 4])
        if c1.button("Forget it", key=key + "_y", type="primary"):
            memory().delete(offer["item_id"])
            st.session_state[key] = f"Forgotten: “{offer['fact']}”"
            st.rerun()
        if c2.button("Keep it", key=key + "_n"):
            st.session_state[key] = f"Kept: “{offer['fact']}”"
            st.rerun()


def question_card(step: dict, key: str):
    if step.get("kind") == "recheck":
        st.markdown("#### Quick re-check")
        st.caption(f"Earlier you told SecondLook: “{step['fact']}”. That was a while ago, and this message asks "
                   "for money, a link or a code, so it checks this is still true before relying on it. "
                   "Answering No makes SecondLook forget it.")
    else:
        st.markdown("#### One quick question")
        st.caption("Your answer changes the verdict. SecondLook asks at most two questions.")
    choice = st.radio(step["question"], step["options"], index=None, key=key)
    return st.button("Answer", disabled=choice is None, type="primary", key=key + "_btn"), choice


# ---------------- sidebar ----------------
with st.sidebar:
    st.title("🔎 SecondLook")
    if use_mock():
        st.warning("MOCK MODE — offline rule-based stand-in. Add your API key in `.env` for real checks.")
    else:
        st.success(f"Live model: {MODEL} ({PROVIDER_LABEL})")
    page = st.radio("Page", ["Check a message", "Study mode"], label_visibility="collapsed")
    st.divider()
    st.subheader("What SecondLook remembers")
    now = dt.datetime.now()
    items = memory().active(now)
    if not items:
        st.caption("Nothing yet. You approve every item before it is saved.")
    for it in items:
        exp = dt.datetime.fromisoformat(it.expires).strftime("%d %b") if it.expires else "never"
        age = it.age_hours(now)
        confirmed = "confirmed today" if age < 24 else f"confirmed {int(age // 24)} day(s) ago"
        c1, c2 = st.columns([4, 1])
        c1.write(f"{it.fact}  \n<span class='small'>{confirmed} · forgets by {exp}</span>",
                 unsafe_allow_html=True)
        if c2.button("✕", key=f"del_{it.id}", help="Delete"):
            memory().delete(it.id)
            st.rerun()
    st.caption("SecondLook forgets on its own: at the expiry date, when a genuine message shows the situation "
               "ended (e.g. “delivered”), or when you say it's no longer true. Facts older than 2 days are "
               "re-checked before they can make a payment, link or code request look safer.")

# ---------------- main page ----------------
if page == "Check a message":
    st.header("Check a suspicious message")
    st.caption("Paste the message. SecondLook checks it against official scam advisories and asks you only what it can't know. "
               "Designed for delivery & e-commerce, bank/OTP/login phishing and job messages.")
    text = st.text_area("Message", height=120, placeholder="e.g. SingPost: We could not deliver your parcel...")
    c1, c2 = st.columns(2)
    channel = c1.selectbox("Received via", ["SMS", "WhatsApp", "Telegram", "Email", "Phone call", "Other"])
    sender = c2.text_input("Sender shown (optional)")
    if st.button("Check message", type="primary", disabled=not text.strip()):
        sess = CheckSession({"id": "ui", "text": text.strip(), "channel": channel, "sender": sender}, memory=memory())
        with st.spinner("Checking against official advisories..."):
            st.session_state.step = run(sess.start())
        st.session_state.sess, st.session_state.text = sess, text.strip()
    step, sess = st.session_state.get("step"), st.session_state.get("sess")
    if step and step["type"] == "question":
        clicked, choice = question_card(step, f"q{len(sess.questions)}")
        if clicked:
            with st.spinner("Updating verdict..."):
                st.session_state.step = run(sess.answer(choice))
            st.rerun()
    elif step and step["type"] == "final":
        show_result(step["result"], st.session_state.text)
    elif step and step["type"] == "error":
        st.error(f"SecondLook couldn't finish this check: {step['error']}")
        if st.button("Retry"):
            sess = CheckSession(sess.message, memory=memory())
            with st.spinner("Checking again..."):
                st.session_state.step = run(sess.start())
            st.session_state.sess = sess
            st.rerun()

else:  # ---------------- study mode ----------------
    study = json.loads((DATA / "study_messages.json").read_text())
    msgs = {m["id"]: m for m in json.loads((DATA / "messages.json").read_text())}
    st.header("Study mode")
    if "study" not in st.session_state:
        pid = st.text_input("Participant ID (e.g. P1)")
        order = st.radio("Order", ["Set A alone, then Set B with SecondLook", "Set B alone, then Set A with SecondLook"])
        st.info("Before starting: read the consent form and the participant card aloud (see study/).")
        if st.button("Start", disabled=not pid, type="primary"):
            a, b = study["set_A"], study["set_B"]
            first, second = (a, b) if order.startswith("Set A") else (b, a)
            st.session_state.study = {"pid": pid, "queue": [(m, "alone") for m in first] + [(m, "with_ai") for m in second],
                                      "i": 0, "t0": None}
            st.rerun()
    else:
        S = st.session_state.study
        st.markdown(f"<div class='small'>Participant card: {html.escape(study['context_card_for_participant'])}</div>",
                    unsafe_allow_html=True)
        if S["i"] >= len(S["queue"]):
            st.success("Done. Thank you! Results saved to runtime/study_log.csv")
        else:
            mid, cond = S["queue"][S["i"]]
            m = msgs[mid]
            S["t0"] = S["t0"] or dt.datetime.now()
            st.subheader(f"Message {S['i'] + 1} of {len(S['queue'])} · {'on your own' if cond == 'alone' else 'with SecondLook'}")
            st.markdown(f"**From:** {html.escape(m['sender'])} ({m['channel']})")
            if cond == "alone":
                st.markdown(f"<div class='msgbox'>{html.escape(m['text'])}</div>", unsafe_allow_html=True)
            else:
                key = f"study_step_{S['i']}"
                planted = {p["message_id"]: p for p in study["planted_wrong_verdicts"]}.get(mid)
                if key not in st.session_state:
                    if planted:  # deliberately wrong verdict to measure over-reliance
                        st.session_state[key] = {"type": "final", "result": {
                            "verdict": planted["verdict"], "red_flags": check_red_flags([], m["text"]),
                            "adjustments": [], "questions": [], "recalled": [], "tokens": 0}}
                    else:
                        st.session_state[key + "_sess"] = CheckSession(m, memory=MemoryStore(mode="off"))
                        with st.spinner("SecondLook is checking..."):
                            st.session_state[key] = run(st.session_state[key + "_sess"].start())
                stp = st.session_state[key]
                if stp["type"] == "question":
                    clicked, choice = question_card(stp, key + "_q")
                    if clicked:
                        st.session_state[key] = run(st.session_state[key + "_sess"].answer(choice))
                        st.rerun()
                    st.stop()
                if stp["type"] == "error":
                    st.error(f"SecondLook couldn't finish this check: {stp['error']}")
                    if st.button("Retry"):
                        del st.session_state[key]
                        st.rerun()
                    st.stop()
                show_result(stp["result"], m["text"], allow_memory=False)
            decision = st.radio("What would you do?", ["Act on it as the message asks (click / pay / reply / share)",
                                                         "Check through the official app or website first",
                                                         "Ignore or delete it", "Report it as a scam"], index=None,
                                key=f"dec_{S['i']}")
            conf = st.slider("How confident are you?", 1, 5, 3, key=f"conf_{S['i']}")
            if st.button("Next", disabled=decision is None, type="primary"):
                log = RUNTIME / "study_log.csv"
                new = not log.exists()
                with open(log, "a", newline="") as f:
                    w = csv.writer(f)
                    if new:
                        w.writerow(["pid", "message_id", "label", "condition", "ai_tier", "planted_wrong",
                                    "decision", "confidence", "seconds"])
                    tier = (st.session_state.get(f"study_step_{S['i']}", {}).get("result", {})
                            .get("verdict", {}).get("tier", ""))
                    w.writerow([S["pid"], mid, m["label"], cond, tier, cond == "with_ai" and mid in {p["message_id"] for p in study["planted_wrong_verdicts"]},
                                decision, conf, round((dt.datetime.now() - S["t0"]).total_seconds())])
                S["i"] += 1
                S["t0"] = None
                st.rerun()
