"""
LLM client: Groq primary, OpenAI fallback.

Uses LangChain's `.with_fallbacks()` runnable wrapper: if the Groq call
raises (rate limit, outage, invalid key, timeout), it transparently retries
the same prompt on OpenAI instead of failing the node.

This is the ONLY place model/provider choice lives -- nodes call
`get_llm(role)` and never instantiate a provider client directly, so
changing providers or models later is a one-file change.

Environment variables:
    GROQ_API_KEY      required (primary provider)
    OPENAI_API_KEY    optional -- enables OpenAI as the fallback.
                      If unset, get_llm() still works, it just has no
                      fallback (a Groq outage will fail the node instead
                      of silently degrading).

Per-role model overrides (all optional, sensible defaults below):
    CODER_MODEL_GROQ, CODER_MODEL_OPENAI
    RESEARCHER_MODEL_GROQ, RESEARCHER_MODEL_OPENAI

NEVER hardcode API keys in this file or anywhere else -- they must only
ever come from environment variables (e.g. a local .env that's gitignored,
or your shell/deployment secrets).
"""

from __future__ import annotations

import os

from langchain_groq import ChatGroq

ROLE_MODELS = {
    "coder": {
        "groq": os.environ.get("CODER_MODEL_GROQ", "llama-3.3-70b-versatile"),
        "openai": os.environ.get("CODER_MODEL_OPENAI", "gpt-4o"),
        "openrouter": os.environ.get("CODER_MODEL_OPENROUTER", "openai/gpt-4o"),
    },
    "researcher": {
        "groq": os.environ.get("RESEARCHER_MODEL_GROQ", "llama-3.1-8b-instant"),
        "openai": os.environ.get("RESEARCHER_MODEL_OPENAI", "gpt-4o-mini"),
        "openrouter": os.environ.get("RESEARCHER_MODEL_OPENROUTER", "openai/gpt-4o-mini"),
    },
}


def _optional_openai(model: str, max_tokens: int):
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        print("[llm_provider] langchain-openai not installed; skipping OpenAI fallback. "
              "Install with: pip install langchain-openai")
        return None
    return ChatOpenAI(model=model, max_completion_tokens=max_tokens)


def _optional_openrouter(model: str, max_tokens: int):
    if not os.environ.get("OPENROUTER_API_KEY"):
        return None
    try:
        from langchain_openai import ChatOpenAI
        from pydantic import SecretStr
    except ImportError:
        print("[llm_provider] langchain-openai not installed; skipping OpenRouter fallback. "
              "Install with: pip install langchain-openai")
        return None
    return ChatOpenAI(
        model=model,
        max_completion_tokens=max_tokens,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        base_url="https://openrouter.ai/api/v1",
    )


def get_llm(role: str, max_tokens: int = 1000):
    """
    Return a runnable LLM for the given role ("coder" or "researcher"):
    Groq as primary, falling back to OpenAI, then OpenRouter if the earlier
    calls fail. Only the keys you set are wired in -- if OPENAI_API_KEY
    isn't set but OPENROUTER_API_KEY is, the chain is Groq → OpenRouter.
    If no fallback keys are set, returns the bare Groq client (no fallback).
    """
    if role not in ROLE_MODELS:
        raise ValueError(f"Unknown role {role!r}; expected one of {list(ROLE_MODELS)}")

    models = ROLE_MODELS[role]

    if not os.environ.get("GROQ_API_KEY"):
        raise RuntimeError(
            "GROQ_API_KEY is not set. Groq is the primary provider for this "
            "project -- set it in your environment (never in code or chat)."
        )
    primary = ChatGroq(model=models["groq"], max_tokens=max_tokens)

    fallbacks = [fb for fb in [
        _optional_openai(models["openai"], max_tokens),
        _optional_openrouter(models["openrouter"], max_tokens),
    ] if fb is not None]

    if not fallbacks:
        return primary

    return primary.with_fallbacks(fallbacks)


def get_model_name(role: str) -> str:
    """Return the primary model name for a role (for cost tracking)."""
    if role not in ROLE_MODELS:
        raise ValueError(f"Unknown role {role!r}; expected one of {list(ROLE_MODELS)}")
    return ROLE_MODELS[role]["groq"]
