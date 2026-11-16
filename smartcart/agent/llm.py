"""LLM provider: Google Gemini (configured in .env).

GEMINI_MODEL           main model           (default gemini-3.5-flash-lite: ~1 s per call)
GEMINI_FALLBACK_MODEL  used automatically if the main model errors, e.g. "503 high demand"
                       (optional; empty = no fallback)
"""
import os
import warnings

from smartcart.db import ROOT  # noqa: F401  (importing smartcart.db loads .env)

DEFAULT_MODEL = "gemini-3.5-flash-lite"

# Newer Gemini models ignore temperature and warn about it on every call.
warnings.filterwarnings("ignore", message=".*uses fixed sampling defaults.*")


class LLMNotConfigured(RuntimeError):
    pass


def _make(model: str):
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=model,
        api_key=os.environ["GOOGLE_API_KEY"],
        temperature=0,      # deterministic tool use where supported; the LLM plans, it doesn't create
        retries=2,
        request_timeout=60,
    )


def get_llm():
    if not os.environ.get("GOOGLE_API_KEY"):
        raise LLMNotConfigured("GOOGLE_API_KEY is not set in .env — get one at https://aistudio.google.com/apikey")
    return _make(os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL)


def get_fallback_llm():
    model = os.environ.get("GEMINI_FALLBACK_MODEL")
    if not model or not os.environ.get("GOOGLE_API_KEY"):
        return None
    return _make(model)
