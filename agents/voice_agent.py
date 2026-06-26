import logging
import shutil
from pathlib import Path

import openai
from elevenlabs.core.api_error import ApiError as ElevenLabsApiError

from core import audio_processor, tts_elevenlabs, tts_google, tts_openai
from core.config import (
    DATA_DIR,
    ELEVENLABS_VOICE_A_FREE_ID,
    ELEVENLABS_VOICE_A_ID,
    ELEVENLABS_VOICE_B_FREE_ID,
    ELEVENLABS_VOICE_B_ID,
    GOOGLE_TTS_VOICE_A,
    GOOGLE_TTS_VOICE_B,
    OPENAI_TTS_VOICE_A,
    OPENAI_TTS_VOICE_B,
    VOICE_PROVIDER,
)
from core.models import PodcastScript

logger = logging.getLogger(__name__)

_FALLBACK: dict[str, str] = {
    "openai": "elevenlabs_free",
    "elevenlabs": "elevenlabs_free",
    "google": "elevenlabs_free",
}


def _voice_id(host: str, provider: str) -> str:
    """Return the configured voice ID for the given host and provider."""
    if provider == "openai":
        return OPENAI_TTS_VOICE_A if host == "A" else OPENAI_TTS_VOICE_B
    elif provider == "google":
        return GOOGLE_TTS_VOICE_A if host == "A" else GOOGLE_TTS_VOICE_B
    elif provider == "elevenlabs_free":
        return ELEVENLABS_VOICE_A_FREE_ID if host == "A" else ELEVENLABS_VOICE_B_FREE_ID
    else:  # elevenlabs — premium library voices
        return ELEVENLABS_VOICE_A_ID if host == "A" else ELEVENLABS_VOICE_B_ID


async def _synthesize(text: str, host: str, provider: str) -> bytes:
    """Route TTS synthesis to the given provider."""
    voice_id = _voice_id(host, provider)
    if provider == "openai":
        return await tts_openai.synthesize(text, voice_id)
    elif provider == "google":
        return await tts_google.synthesize(text, voice_id)
    else:  # elevenlabs or elevenlabs_free — same API, different voice IDs
        return await tts_elevenlabs.synthesize(text, voice_id)


def _is_billing_error(exc: Exception) -> bool:
    """Return True if the error is a quota/billing failure (not a transient rate limit)."""
    if isinstance(exc, openai.RateLimitError) and "insufficient_quota" in str(exc):
        return True
    if isinstance(exc, ElevenLabsApiError) and exc.status_code == 402:
        return True
    return False


async def run(script: PodcastScript) -> tuple[Path, int, str, list[dict]]:
    """Generate audio for each dialogue turn, stitch into final MP3.

    Returns (output_path, total_chars, provider_used, segments) where segments is a list of
    {"start": float, "end": float, "paper_refs": list[str]} dicts aligned to each dialogue turn.
    """
    episode_id = script.episode_id
    provider = VOICE_PROVIDER
    logger.info("VoiceAgent: provider=%s, episode=%s", provider, episode_id)

    segment_dir = DATA_DIR / "audio" / "segments" / episode_id
    segment_dir.mkdir(parents=True, exist_ok=True)

    segment_paths: list[Path] = []
    total_chars = 0

    for idx, turn in enumerate(script.turns):
        segment_path = segment_dir / f"{idx:03d}_{turn.host}.mp3"
        logger.info(
            "VoiceAgent: generating turn %d/%d (host=%s, chars=%d)",
            idx + 1, len(script.turns), turn.host, len(turn.text),
        )

        try:
            audio_bytes = await _synthesize(turn.text, turn.host, provider)
        except Exception as exc:
            if _is_billing_error(exc) and provider in _FALLBACK:
                fallback = _FALLBACK[provider]
                logger.warning(
                    "VoiceAgent: %s billing error on turn %d, switching to %s for remaining turns",
                    provider, idx + 1, fallback,
                )
                provider = fallback
                audio_bytes = await _synthesize(turn.text, turn.host, provider)
            else:
                raise

        segment_path.write_bytes(audio_bytes)
        turn.audio_segment_path = segment_path
        segment_paths.append(segment_path)
        total_chars += len(turn.text)

    output_path = DATA_DIR / "audio" / f"{episode_id}.mp3"
    _, timings = audio_processor.stitch_episode(segment_paths, output_path)
    logger.info("VoiceAgent: episode assembled at %s", output_path)

    segments = [
        {
            "start": round(start, 3),
            "end":   round(end, 3),
            "paper_refs": turn.paper_refs,
        }
        for turn, (start, end) in zip(script.turns, timings)
    ]

    shutil.rmtree(segment_dir)
    logger.info("VoiceAgent: cleaned up %d segment files", len(segment_paths))

    return output_path, total_chars, provider, segments
