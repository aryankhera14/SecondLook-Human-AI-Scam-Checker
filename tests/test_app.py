"""Headless UI test of the real Streamlit script (mock model)."""
from streamlit.testing.v1 import AppTest


def test_check_question_verdict_and_memory(tmp_path, monkeypatch):
    monkeypatch.setattr("secondlook.config.RUNTIME", tmp_path)
    at = AppTest.from_file("../app.py", default_timeout=60).run()
    at.text_area[0].input("Ninja Van: Your COD parcel (SGD 48.90) will arrive today between 2-6pm. Please prepare exact cash for the driver.").run()
    at.button[0].click().run()  # Check message
    assert any("expecting a delivery" in r.label for r in at.radio)
    q = [r for r in at.radio if "expecting" in r.label][0]
    q.set_value("Yes").run()
    [b for b in at.button if b.label == "Answer"][0].click().run()
    body = " ".join(m.value for m in at.markdown)
    assert "Probably genuine" in body and "What to do next" in body
    [r for r in at.radio if r.label == "Remember for"][0].set_value(14).run()
    [b for b in at.button if b.label == "Save"][0].click().run()
    items = at.session_state.memory.items
    assert items and (items[0].expires[:10] > items[0].created[:10]), "approved memory should be stored"
    assert not at.exception


def test_delivered_message_shows_forget_offer(tmp_path, monkeypatch):
    import datetime as dt
    from secondlook.memory import MemoryStore
    monkeypatch.setattr("secondlook.config.RUNTIME", tmp_path)
    mem = MemoryStore(tmp_path / "memory.json", mode="adaptive")
    mem.add({"fact": "I am expecting a parcel delivery", "context_key": "expecting_delivery", "value": True}, dt.datetime.now())
    at = AppTest.from_file("../app.py", default_timeout=60).run()
    at.text_area[0].input("J&T Express: Your parcel JT0042 has been delivered to your doorstep.").run()
    at.button[0].click().run()
    assert "Forget" in " ".join(m.value for m in at.markdown)
    [b for b in at.button if b.label == "Forget it"][0].click().run()
    assert at.session_state.memory.items == []
    assert not at.exception


def test_study_mode_planted_verdict(tmp_path, monkeypatch):
    monkeypatch.setattr("secondlook.config.RUNTIME", tmp_path)
    at = AppTest.from_file("../app.py", default_timeout=60).run()
    at.sidebar.radio[0].set_value("Study mode").run()
    at.text_input[0].input("P0").run()
    [r for r in at.radio if r.label == "Order"][0].set_value("Set B alone, then Set A with SecondLook").run()
    [b for b in at.button if b.label == "Start"][0].click().run()
    for _ in range(4):  # four messages alone
        [r for r in at.radio if r.label == "What would you do?"][0].set_value("Ignore or delete it").run()
        [b for b in at.button if b.label == "Next"][0].click().run()
    assert "with SecondLook" in " ".join(s.value for s in at.subheader)
    seen_planted = False
    for _ in range(4):  # four messages with SecondLook; answer any question, then decide
        for _q in range(3):
            qs = [r for r in at.radio if r.label != "What would you do?" and r.label not in ("Page",)]
            ans = [b for b in at.button if b.label == "Answer"]
            if not ans:
                break
            qs[-1].set_value("No").run(); ans[0].click().run()
        body = " ".join(m.value for m in at.markdown)
        seen_planted |= "normal cash-on-delivery notice" in body
        [r for r in at.radio if r.label == "What would you do?"][0].set_value("Report it as a scam").run()
        [b for b in at.button if b.label == "Next"][0].click().run()
    assert seen_planted, "Set A with SecondLook must include its planted wrong verdict"
    log = (tmp_path / "study_log.csv").read_text().splitlines()
    assert len(log) == 9 and log[0].startswith("pid")
    assert not at.exception
