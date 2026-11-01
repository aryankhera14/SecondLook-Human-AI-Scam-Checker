import json
from typing import get_args

from secondlook.config import DATA
from secondlook.schemas import ContextKey


def test_dataset_shape():
    msgs = json.loads((DATA / "messages.json").read_text())
    assert len(msgs) == 40 and len({m["id"] for m in msgs}) == 40
    keys = set(get_args(ContextKey))
    for m in msgs:
        assert m["label"] in ("scam", "legit")
        assert set(m["context"]) <= keys
        assert m["topic"] in ("delivery_ecommerce", "phishing", "job", "out_of_scope", "everyday")


def test_focus_types_cover_17_of_20_scams():
    msgs = json.loads((DATA / "messages.json").read_text())
    focus = [m for m in msgs if m["label"] == "scam" and m["topic"] in ("delivery_ecommerce", "phishing", "job")]
    assert len(focus) == 17


def test_context_pairs_share_text_but_not_label():
    msgs = [m for m in json.loads((DATA / "messages.json").read_text()) if m["pair_id"]]
    pairs = {}
    for m in msgs:
        pairs.setdefault(m["pair_id"], []).append(m)
    for a, b in pairs.values():
        assert a["text"] == b["text"] and a["label"] != b["label"]


def test_study_ids_exist():
    ids = {m["id"] for m in json.loads((DATA / "messages.json").read_text())}
    s = json.loads((DATA / "study_messages.json").read_text())
    planted = [p["message_id"] for p in s["planted_wrong_verdicts"]]
    assert set(s["set_A"] + s["set_B"]) <= ids
    assert sum(p in s["set_A"] for p in planted) == 1 and sum(p in s["set_B"] for p in planted) == 1


def test_memory_scenario_has_early_arrival_and_silent_arrival():
    sc = json.loads((DATA / "memory_scenario.json").read_text())["sessions"]
    assert any(s.get("completes") for s in sc)
    assert sum(s["label"] == "scam" and "COD" in s["text"] for s in sc) == 2
