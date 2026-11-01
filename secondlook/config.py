"""Configuration. Put your key in .env (copy .env.example). Never commit .env."""
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RUNTIME = ROOT / "runtime"
RUNTIME.mkdir(exist_ok=True)

try:  # python-dotenv is optional at import time so tests run without it
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:  # pragma: no cover
    pass

# Model served by Groq. (OPENAI_MODEL is the variable name kept from the first version.)
MODEL = os.getenv("GROQ_MODEL") or os.getenv("OPENAI_MODEL") or "openai/gpt-oss-120b"
MAX_QUESTIONS = int(os.getenv("SECONDLOOK_MAX_QUESTIONS", "2"))
# Low temperature keeps evaluation runs comparable; raise it for a livelier demo if you like.
TEMPERATURE = float(os.getenv("SECONDLOOK_TEMPERATURE", "0.2"))
# gpt-oss models think before answering; "low" cuts tokens per check roughly in half, which matters on
# Groq's free tier (8,000 tokens/minute, 200,000/day). Set to "medium" or "" to change or disable.
REASONING_EFFORT = os.getenv("SECONDLOOK_REASONING_EFFORT", "low")


# Provider: "groq" (default) or "openrouter" (same model, OpenAI-compatible API; key in OPENROUTER_API_KEY).
PROVIDER = os.getenv("SECONDLOOK_PROVIDER", "groq").strip().lower()
PROVIDER_LABEL = {"groq": "Groq", "openrouter": "OpenRouter"}.get(PROVIDER, PROVIDER)


def openrouter_key() -> str | None:
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    return key if key and "REPLACE" not in key.upper() else None


def groq_key() -> str | None:
    """GROQ_API_KEY, or a Groq key (gsk_...) placed in OPENAI_API_KEY by mistake."""
    for name in ("GROQ_API_KEY", "OPENAI_API_KEY"):
        key = os.getenv(name, "").strip()
        if key and "REPLACE" not in key.upper() and (name == "GROQ_API_KEY" or key.startswith("gsk_")):
            return key
    return None


def api_key_present() -> bool:
    return (openrouter_key() if PROVIDER == "openrouter" else groq_key()) is not None


def use_mock() -> bool:
    """Mock mode runs the whole app offline with a rule-based stand-in model.
    It is used for tests and demos only; its results are NOT real findings."""
    return os.getenv("SECONDLOOK_MOCK", "0") == "1" or not api_key_present()
