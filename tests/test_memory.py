import datetime as dt
import json

from secondlook.memory import MemoryStore

NOW = dt.datetime(2026, 10, 5)
SUG = {"fact": "I am expecting a parcel", "context_key": "expecting_delivery", "value": True,
       "applies_to": ["delivery"]}


def test_default_lifetime_is_set_by_app_not_model():
    m = MemoryStore(mode="expiring")
    item = m.add({**SUG, "days_valid": 365}, NOW)
    assert dt.datetime.fromisoformat(item.expires) == NOW + dt.timedelta(days=5)


def test_user_chosen_lifetime():
    item = MemoryStore(mode="adaptive").add(SUG, NOW, days=14)
    assert dt.datetime.fromisoformat(item.expires) == NOW + dt.timedelta(days=14)


def test_expiring_memory_expires():
    m = MemoryStore(mode="expiring")
    m.add(SUG, NOW)
    assert m.active(NOW + dt.timedelta(days=4), "delivery")
    assert not m.active(NOW + dt.timedelta(days=6), "delivery")


def test_memory_is_scoped_to_message_type():
    m = MemoryStore(mode="adaptive")
    m.add(SUG, NOW)
    assert m.active(NOW, "ecommerce") and not m.active(NOW, "job")


def test_one_off_and_unknown_facts_are_never_stored():
    m = MemoryStore(mode="adaptive")
    assert m.add({**SUG, "context_key": "requested_otp_or_login"}, NOW) is None
    assert m.add({**SUG, "context_key": "unknown_personal_inquiry"}, NOW) is None
    assert m.items == []


def test_invalid_legacy_entries_are_dropped_on_load(tmp_path):
    path = tmp_path / "memory.json"
    path.write_text(json.dumps([{"id": "x", "fact": "Received an unsolicited personal inquiry",
                                 "context_key": "unknown_personal_inquiry", "value": True,
                                 "applies_to": ["personal"], "created": NOW.isoformat(), "expires": None}]))
    assert MemoryStore(path).items == []


def test_permanent_never_expires_and_off_stores_nothing():
    p = MemoryStore(mode="permanent"); p.add(SUG, NOW)
    assert p.active(NOW + dt.timedelta(days=400), "delivery")
    o = MemoryStore(mode="off"); o.add(SUG, NOW)
    assert o.items == []


def test_persist_and_delete(tmp_path):
    path = tmp_path / "m.json"
    m = MemoryStore(path); item = m.add(SUG, NOW)
    assert MemoryStore(path).items[0].fact == SUG["fact"]
    m.delete(item.id)
    assert MemoryStore(path).items == []
