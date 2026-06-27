"""Provider abstraction layer for LLM calls.

Route each pipeline stage to Anthropic / OpenAI / Gemini independently via env vars:
    LLM_PROVIDER_SCRIPT=anthropic        (default)
    LLM_PROVIDER_BIBLIOGRAPHY=anthropic  (default)
    LLM_PROVIDER_REASONING=anthropic     (default)
    LLM_PROVIDER_GRAPH=anthropic         (default)

Model tier is derived from curation_level so higher-effort episodes get better models:
    auto / keyword_guided  → cheap   (Haiku / gpt-4o-mini / gemini-flash)
    context / anchor       → standard (Sonnet / gpt-4o / gemini-pro)
    fully_guided           → premium  (Sonnet / gpt-4o / gemini-pro)

Key resolution order (per call):
    1. Check user_provider_assignments for A/B provider override
    2. Check user_api_keys for active BYOK key → use it, skip credit debit
    3. Fall back to platform key pool (round-robin across PROVIDER_KEY_1, _2, ...)
    4. Log every call to llm_calls telemetry table
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

Stage = Literal["script", "bibliography", "annotation", "reasoning", "graph"]

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
    "graph":        "LLM_PROVIDER_GRAPH",
}


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    provider: str
    model: str
    key_source: str = "platform"  # 'byok' | 'platform'
    key_index: int | None = None


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


def _get_ab_provider(user_id: str, stage: str, db_url: str) -> str | None:
    """Return stored A/B provider assignment for this user+stage, or None."""
    try:
        import psycopg
        with psycopg.connect(db_url) as conn:
            row = conn.execute(
                "SELECT provider FROM user_provider_assignments WHERE user_id = %s AND stage = %s",
                (user_id, stage),
            ).fetchone()
        return row[0] if row else None
    except Exception as exc:
        logger.warning("A/B provider lookup failed: %s", exc)
        return None


def _store_ab_provider(user_id: str, stage: str, provider: str, db_url: str) -> None:
    """Persist a deterministic provider assignment for a user+stage."""
    try:
        import psycopg
        with psycopg.connect(db_url) as conn:
            conn.execute(
                """
                INSERT INTO user_provider_assignments (user_id, stage, provider)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, stage) DO NOTHING
                """,
                (user_id, stage, provider),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("A/B provider store failed: %s", exc)


def _assign_ab_provider(user_id: str, stage: str, db_url: str) -> str | None:
    """Hash user_id to pick a provider for A/B; persist and return it.

    Only used when multiple LLM providers are configured for a stage
    (future capability). Currently returns None so env-var routing wins.
    """
    existing = _get_ab_provider(user_id, stage, db_url)
    if existing:
        return existing
    # Deterministic hash → provider slot (extend when A/B is active)
    providers = _get_stage_providers(stage)
    if len(providers) < 2:
        return None
    slot = int(hashlib.md5(f"{user_id}:{stage}".encode()).hexdigest(), 16) % len(providers)
    chosen = providers[slot]
    _store_ab_provider(user_id, stage, chosen, db_url)
    return chosen


def _get_stage_providers(stage: str) -> list[str]:
    """Return list of configured providers for a stage (for future A/B support)."""
    env_key = _STAGE_ENV.get(stage, "LLM_PROVIDER_SCRIPT")
    primary = os.getenv(env_key, "anthropic")
    return [primary]


def _log_llm_call(
    *,
    episode_id: str | None,
    user_id: str | None,
    stage: str,
    provider: str,
    model: str,
    key_source: str,
    key_index: int | None,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    db_url: str,
) -> None:
    try:
        import psycopg
        with psycopg.connect(db_url) as conn:
            conn.execute(
                """
                INSERT INTO llm_calls
                  (episode_id, user_id, stage, provider, model,
                   key_source, key_index, input_tokens, output_tokens, latency_ms)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (episode_id, user_id, stage, provider, model,
                 key_source, key_index, input_tokens, output_tokens, latency_ms),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("llm_calls telemetry write failed: %s", exc)


def chat(
    messages: list[dict],
    max_tokens: int,
    stage: Stage,
    curation_level: str = "auto",
    system: str | None = None,
    tier_override: str | None = None,
    user_id: str | None = None,
    episode_id: str | None = None,
) -> LLMResponse:
    """Route and execute a synchronous LLM chat call. Returns normalized LLMResponse.

    Key resolution:
      - If user_id provided: check BYOK key → use it (key_source='byok')
      - Otherwise: round-robin platform key pool (key_source='platform')
    Logs every call to llm_calls table when DATABASE_URL is set.
    """
    provider, model = route(stage, curation_level)
    if tier_override and tier_override in _PROVIDER_MODELS.get(provider, {}):
        model = _PROVIDER_MODELS[provider][tier_override]

    db_url = os.getenv("DATABASE_URL", "")

    # A/B provider override (future; currently a no-op when only one provider configured)
    if user_id and db_url:
        ab = _assign_ab_provider(user_id, stage, db_url)
        if ab and ab in _PROVIDER_MODELS:
            provider = ab
            tier = _CURATION_TIER.get(curation_level, "standard")
            model = _PROVIDER_MODELS[provider][tier_override or tier]

    # Key resolution
    byok_key: str | None = None
    key_source = "platform"
    key_index: int | None = None

    if user_id and db_url:
        from core.byok import get_user_key
        byok_key = get_user_key(user_id, provider, db_url)
        if byok_key:
            key_source = "byok"

    logger.info(
        "llm.chat stage=%s curation=%s provider=%s model=%s key_source=%s",
        stage, curation_level, provider, model, key_source,
    )

    t0 = time.monotonic()

    if provider == "anthropic":
        resp, key_index = _anthropic_chat(messages, system, max_tokens, model, provider, byok_key)
    elif provider == "openai":
        resp, key_index = _openai_chat(messages, system, max_tokens, model, provider, byok_key)
    elif provider == "gemini":
        resp, key_index = _gemini_chat(messages, system, max_tokens, model, provider, byok_key)
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    latency_ms = int((time.monotonic() - t0) * 1000)

    resp.key_source = key_source
    resp.key_index = key_index

    if db_url:
        _log_llm_call(
            episode_id=episode_id,
            user_id=user_id,
            stage=stage,
            provider=provider,
            model=model,
            key_source=key_source,
            key_index=key_index,
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
            latency_ms=latency_ms,
            db_url=db_url,
        )

    return resp


def _anthropic_chat(
    messages: list[dict],
    system: str | None,
    max_tokens: int,
    model: str,
    provider: str,
    byok_key: str | None = None,
) -> tuple[LLMResponse, int | None]:
    import anthropic as _anthropic
    resolved_index: int | None = None
    if byok_key:
        api_key = byok_key
    else:
        from core.key_pool import get_platform_key
        api_key, resolved_index = get_platform_key("anthropic")
    client = _anthropic.Anthropic(api_key=api_key)
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
    ), resolved_index


def _openai_chat(
    messages: list[dict],
    system: str | None,
    max_tokens: int,
    model: str,
    provider: str,
    byok_key: str | None = None,
) -> tuple[LLMResponse, int | None]:
    from openai import OpenAI
    resolved_index: int | None = None
    if byok_key:
        api_key = byok_key
    else:
        from core.key_pool import get_platform_key
        api_key, resolved_index = get_platform_key("openai")
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
    ), resolved_index


def _gemini_chat(
    messages: list[dict],
    system: str | None,
    max_tokens: int,
    model: str,
    provider: str,
    byok_key: str | None = None,
) -> tuple[LLMResponse, int | None]:
    try:
        import google.generativeai as genai
    except ImportError:
        raise ImportError(
            "google-generativeai is not installed. "
            "Run: pip install google-generativeai"
        )
    resolved_index: int | None = None
    if byok_key:
        api_key = byok_key
    else:
        from core.key_pool import get_platform_key
        api_key, resolved_index = get_platform_key("gemini")
    genai.configure(api_key=api_key)

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
    ), resolved_index
