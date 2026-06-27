"""Provider abstraction layer for LLM calls.

Route each pipeline stage to Anthropic / OpenAI / Gemini independently via env vars:
    LLM_PROVIDER_SCRIPT=anthropic        (default)
    LLM_PROVIDER_BIBLIOGRAPHY=anthropic  (default)
    LLM_PROVIDER_REASONING=anthropic     (default)

Model tier is derived from curation_level so higher-effort episodes get better models:
    auto / keyword_guided  → cheap   (Haiku / gpt-4o-mini / gemini-flash)
    context / anchor       → standard (Sonnet / gpt-4o / gemini-pro)
    fully_guided           → premium  (Sonnet / gpt-4o / gemini-pro)
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

Stage = Literal["script", "bibliography", "annotation", "reasoning"]

_PROVIDER_MODELS: dict[str, dict[str, str]] = {
    "anthropic": {
        "cheap":    "claude-haiku-4-5-20251001",
        "standard": "claude-sonnet-4-6",
        "premium":  "claude-sonnet-4-6",
    },
    "openai": {
        "cheap":    "gpt-4o-mini",
        "standard": "gpt-4o",
        "premium":  "gpt-4o",
    },
    "gemini": {
        "cheap":    "gemini-1.5-flash",
        "standard": "gemini-1.5-pro",
        "premium":  "gemini-1.5-pro",
    },
}

_CURATION_TIER: dict[str, str] = {
    "auto":           "cheap",
    "keyword_guided": "cheap",
    "context_guided": "standard",
    "anchor_guided":  "standard",
    "fully_guided":   "premium",
}

_STAGE_ENV: dict[str, str] = {
    "script":       "LLM_PROVIDER_SCRIPT",
    "bibliography": "LLM_PROVIDER_BIBLIOGRAPHY",
    "annotation":   "LLM_PROVIDER_BIBLIOGRAPHY",
    "reasoning":    "LLM_PROVIDER_REASONING",
}


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    provider: str
    model: str


def route(stage: Stage, curation_level: str = "auto") -> tuple[str, str]:
    """Return (provider, model) for a stage + curation_level pair."""
    tier = _CURATION_TIER.get(curation_level, "standard")
    env_key = _STAGE_ENV.get(stage, "LLM_PROVIDER_SCRIPT")
    provider = os.getenv(env_key, "anthropic")
    if provider not in _PROVIDER_MODELS:
        logger.warning("Unknown LLM provider '%s' for stage '%s', falling back to anthropic", provider, stage)
        provider = "anthropic"
    model = _PROVIDER_MODELS[provider][tier]
    return provider, model


def chat(
    messages: list[dict],
    max_tokens: int,
    stage: Stage,
    curation_level: str = "auto",
    system: str | None = None,
    tier_override: str | None = None,
) -> LLMResponse:
    """Route and execute a synchronous LLM chat call. Returns normalized LLMResponse."""
    provider, model = route(stage, curation_level)
    if tier_override and tier_override in _PROVIDER_MODELS.get(provider, {}):
        model = _PROVIDER_MODELS[provider][tier_override]

    logger.info("llm.chat stage=%s curation=%s provider=%s model=%s", stage, curation_level, provider, model)

    if provider == "anthropic":
        return _anthropic_chat(messages, system, max_tokens, model, provider)
    if provider == "openai":
        return _openai_chat(messages, system, max_tokens, model, provider)
    if provider == "gemini":
        return _gemini_chat(messages, system, max_tokens, model, provider)
    raise ValueError(f"Unsupported provider: {provider}")


def _anthropic_chat(
    messages: list[dict],
    system: str | None,
    max_tokens: int,
    model: str,
    provider: str,
) -> LLMResponse:
    import anthropic as _anthropic
    from core.config import ANTHROPIC_API_KEY
    client = _anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    kwargs: dict = {"model": model, "max_tokens": max_tokens, "messages": messages}
    if system:
        kwargs["system"] = system
    resp = client.messages.create(**kwargs)
    return LLMResponse(
        text=resp.content[0].text,
        input_tokens=resp.usage.input_tokens,
        output_tokens=resp.usage.output_tokens,
        provider=provider,
        model=model,
    )


def _openai_chat(
    messages: list[dict],
    system: str | None,
    max_tokens: int,
    model: str,
    provider: str,
) -> LLMResponse:
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set — cannot use openai provider")
    client = OpenAI(api_key=api_key)
    all_msgs = ([{"role": "system", "content": system}] if system else []) + messages
    resp = client.chat.completions.create(
        model=model,
        max_completion_tokens=max_tokens,
        messages=all_msgs,
    )
    return LLMResponse(
        text=resp.choices[0].message.content or "",
        input_tokens=resp.usage.prompt_tokens,
        output_tokens=resp.usage.completion_tokens,
        provider=provider,
        model=model,
    )


def _gemini_chat(
    messages: list[dict],
    system: str | None,
    max_tokens: int,
    model: str,
    provider: str,
) -> LLMResponse:
    try:
        import google.generativeai as genai  # pip install google-generativeai
    except ImportError:
        raise ImportError(
            "google-generativeai is not installed. "
            "Run: pip install google-generativeai"
        )
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set — cannot use gemini provider")
    genai.configure(api_key=api_key)

    # Flatten to last user message (multi-turn support not needed for current call sites)
    user_text = next(
        (m["content"] for m in reversed(messages) if m.get("role") == "user"), ""
    )
    gen_config = genai.GenerationConfig(max_output_tokens=max_tokens)
    gmodel = genai.GenerativeModel(
        model,
        system_instruction=system,
        generation_config=gen_config,
    )
    resp = gmodel.generate_content(user_text)
    usage = resp.usage_metadata
    return LLMResponse(
        text=resp.text,
        input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
        output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
        provider=provider,
        model=model,
    )
