"""One live check to confirm your key and model work:   python -m secondlook.selfcheck"""
import asyncio
import json

from .agent import run_check
from .config import DATA, MODEL, PROVIDER_LABEL, api_key_present, use_mock


def main():
    if use_mock():
        print(f"Mock mode is on (SECONDLOOK_MOCK=1 or no real key for {PROVIDER_LABEL} in .env).")
        if not api_key_present():
            print("-> In .env set GROQ_API_KEY=gsk_... (or SECONDLOOK_PROVIDER=openrouter and OPENROUTER_API_KEY=sk-or-...), "
                  "and SECONDLOOK_MOCK=0.")
        return
    msg = {m["id"]: m for m in json.loads((DATA / "messages.json").read_text())}["CD06b"]
    print(f"Calling {MODEL} on {PROVIDER_LABEL} once...")
    res = asyncio.run(run_check(msg, "secondlook", lambda q: (print("  asked:", q["question"], "-> No"), "No")[1]))
    v = res["verdict"]
    print(f"  tier: {v['tier']}\n  summary: {v['summary']}\n  next step: {v['safe_next_step']}\n  tokens: {res['tokens']}")
    print("OK - live mode works.")


if __name__ == "__main__":
    main()
