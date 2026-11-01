"""Helpers for recording the demo video (they only touch runtime/memory.json).

    python -m secondlook.demo_tools show          # list remembered facts
    python -m secondlook.demo_tools age 3         # pretend saved facts were confirmed 3 days ago
    python -m secondlook.demo_tools reset         # forget everything

`age` lets you show the re-check ("Are you still expecting a parcel?") without waiting 48 hours.
Expiry dates are left unchanged, so the facts stay active.
"""
import datetime as dt
import sys

from .config import RUNTIME
from .memory import MemoryStore


def main(argv):
    store = MemoryStore(RUNTIME / "memory.json", mode="adaptive")
    cmd = argv[0] if argv else "show"
    if cmd == "age":
        days = float(argv[1]) if len(argv) > 1 else 3
        for item in store.items:
            for attr in ("created", "last_confirmed"):
                if getattr(item, attr):
                    setattr(item, attr, (dt.datetime.fromisoformat(getattr(item, attr)) - dt.timedelta(days=days)).isoformat())
        store._save()
        print(f"Aged {len(store.items)} fact(s) by {days:g} day(s). Restart or refresh the app.")
    elif cmd == "reset":
        store.clear()
        print("Memory cleared.")
    for item in store.items:
        print(f"- {item.fact} | confirmed {item.last_confirmed or item.created} | expires {item.expires}")
    if not store.items:
        print("(no remembered facts)")


if __name__ == "__main__":
    main(sys.argv[1:])
