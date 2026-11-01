"""The four automatic forgetting layers (professor's feedback: when should the agent forget?)."""
import asyncio
import datetime as dt

from secondlook.agent import run_check
from secondlook.memory import MemoryStore

T0 = dt.datetime(2026, 10, 5, 9)
SUG = {"fact": "I am expecting a parcel delivery", "context_key": "expecting_delivery", "value": True,
       "applies_to": ["delivery"]}
COD = {"id": "c", "channel": "SMS", "sender": "",
       "text": "Ninja Van: Your COD parcel (SGD 48.90) will arrive today between 2-6pm. Please prepare exact cash for the driver."}
DELIVERED = {"id": "d", "channel": "SMS", "sender": "", "text": "J&T Express: Your parcel JT0042 has been delivered to your doorstep."}


def check(msg, mem, now, answer="No", forget=False):
    asked = []
    res = asyncio.run(run_check(msg, "secondlook", lambda q: (asked.append(q), answer)[1], mem, now,
                                forget_fn=lambda o: forget))
    return res, asked


def test_fresh_memory_skips_the_question():
    mem = MemoryStore(mode="adaptive"); mem.add(SUG, T0)
    res, asked = check(COD, mem, T0 + dt.timedelta(hours=20))
    assert asked == [] and res["recalled"]


def test_old_memory_is_rechecked_before_relaxing_caution_and_no_forgets_it():
    mem = MemoryStore(mode="adaptive"); mem.add(SUG, T0)
    res, asked = check(COD, mem, T0 + dt.timedelta(days=3), answer="No")
    assert asked[0]["kind"] == "recheck"
    assert res["verdict"]["tier"] == "likely_scam" and mem.items == []


def test_recheck_yes_renews_the_memory():
    mem = MemoryStore(mode="adaptive"); mem.add(SUG, T0)
    later = T0 + dt.timedelta(days=3)
    check(COD, mem, later, answer="Yes")
    item = mem.items[0]
    assert item.last_confirmed == later.isoformat()
    assert dt.datetime.fromisoformat(item.expires) == later + dt.timedelta(days=5)


def test_no_recheck_when_message_asks_for_nothing_risky():
    mem = MemoryStore(mode="adaptive"); mem.add(SUG, T0)
    _, asked = check(DELIVERED, mem, T0 + dt.timedelta(days=3))
    assert not any(q.get("kind") == "recheck" for q in asked)


def test_fixed_expiry_does_not_recheck():
    mem = MemoryStore(mode="expiring"); mem.add(SUG, T0)
    res, asked = check(COD, mem, T0 + dt.timedelta(days=3))
    assert asked == [] and res["verdict"]["tier"] != "likely_scam"  # the weakness adaptive fixes


def test_delivered_message_offers_to_forget():
    mem = MemoryStore(mode="adaptive"); mem.add(SUG, T0)
    res, _ = check(DELIVERED, mem, T0 + dt.timedelta(hours=5), forget=True)
    assert res["forget_offers"] and mem.items == []


def test_a_scam_cannot_trigger_forgetting():
    mem = MemoryStore(mode="adaptive"); mem.add(SUG, T0)
    assert mem.completion_offers(DELIVERED["text"], "likely_scam", T0) == []


def test_contradicting_answer_forgets():
    mem = MemoryStore(mode="adaptive"); mem.add(SUG, T0)
    assert mem.apply_answer("expecting_delivery", False, T0) == "forgotten" and mem.items == []
