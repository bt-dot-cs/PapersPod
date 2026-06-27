"""Platform API key pool — round-robin selection across numbered env vars.

Convention: ANTHROPIC_API_KEY_1, ANTHROPIC_API_KEY_2, ...
Falls back to ANTHROPIC_API_KEY (no suffix) if no numbered keys exist.
"""
from __future__ import annotations

import itertools
import logging
import os
import threading

logger = logging.getLogger(__name__)

_PROVIDER_ENV_PREFIX: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai":    "OPENAI_API_KEY",
    "gemini":    "GOOGLE_API_KEY",
}

# Per-provider round-robin counters — atomic via threading.Lock
_counters: dict[str, itertools.count] = {}
_locks: dict[str, threading.Lock] = {}


def _discover_keys(provider: str) -> list[tuple[int, str]]:
    """Return [(index, key), ...] for a provider, sorted by index.

    Scans PREFIX_1, PREFIX_2, ... up to 20. Falls back to PREFIX (index 0)
    if no numbered keys are set.
    """
    prefix = _PROVIDER_ENV_PREFIX.get(provider)
    if not prefix:
        raise ValueError(f"Unknown provider: {provider}")

    found: list[tuple[int, str]] = []
    for i in range(1, 21):
        val = os.getenv(f"{prefix}_{i}", "").strip()
        if val:
            found.append((i, val))

    if not found:
        fallback = os.getenv(prefix, "").strip()
        if fallback:
            found.append((0, fallback))

    return found


def get_platform_key(provider: str) -> tuple[str, int]:
    """Return (api_key, key_index) for the next slot in the round-robin.

    Raises RuntimeError if no keys are configured for the provider.
    """
    keys = _discover_keys(provider)
    if not keys:
        raise RuntimeError(
            f"No API key configured for provider '{provider}'. "
            f"Set {_PROVIDER_ENV_PREFIX.get(provider, 'KEY')} or "
            f"{_PROVIDER_ENV_PREFIX.get(provider, 'KEY')}_1 etc."
        )

    if provider not in _locks:
        _locks[provider] = threading.Lock()
        _counters[provider] = itertools.count()

    with _locks[provider]:
        slot = next(_counters[provider]) % len(keys)

    index, key = keys[slot]
    logger.debug("key_pool: provider=%s slot=%d key_index=%d", provider, slot, index)
    return key, index
