import logging
from pathlib import Path

from core import audio_processor, tts_elevenlabs, tts_google, tts_openai
from core.config import (
    DATA_DIR,
    ELEVENLABS_VOICE_A_ID,
    ELEVENLABS_VOICE_B_ID,
    GOOGLE_TTS_VOICE_A,
    GOOGLE_TTS_VOICE_B,
    OPENAI_TTS_VOICE_A,
    OPENAI_TTS_VOICE_B,
    VOICE_PROVIDER,
)
from core.models import PodcastScript

logger = logging.getLogger(__name__)


def _voice_id(host: str) -> str:
    """Return the configured voice ID for the given host and active provider."""
    if VOICE_PROVIDER == "openai":
        return OPENAI_TTS_VOICE_A if host == "A" else OPENAI_TTS_VOICE_B
    elif VOICE_PROVIDER == "google":
        return GOOGLE_TTS_VOICE_A if host == "A" else GOOGLE_TTS_VOICE_B
    else:
        return ELEVENLABS_VOICE_A_ID if host == "A" else ELEVENLABS_VOICE_B_ID


async def _synthesize(text: str, host: str) -> bytes:
    """Route TTS synthesis to the configured provider."""
    voice_id = _voice_id(host)
    if VOICE_PROVIDER == "openai":
        return await tts_openai.synthesize(text, voice_id)
    elif VOICE_PROVIDER == "google":
        return await tts_google.synthesize(text, voice_id)
    else:
        return await tts_elevenlabs.synthesize(text, voice_id)


async def run(script: PodcastScript) -> Path:
    """Generate audio for each dialogue turn, stitch into final MP3."""
    episode_id = script.episode_id
    logger.info("VoiceAgent: provider=%s, episode=%s", VOICE_PROVIDER, episode_id)

    segment_dir = DATA_DIR / "audio" / "segments" / episode_id
    segment_dir.mkdir(parents=True, exist_ok=True)

    segment_paths: list[Path] = []

    for idx, turn in enumerate(script.turns):
        segment_path = segment_dir / f"{idx:03d}_{turn.host}.mp3"
        logger.info(
            "VoiceAgent: generating turn %d/%d (host=%s, chars=%d)",
            idx + 1, len(script.turns), turn.host, len(turn.text),
        )

        audio_bytes = await _synthesize(turn.text, turn.host)
        segment_path.write_bytes(audio_bytes)
        turn.audio_segment_path = segment_path
        segment_paths.append(segment_path)

    output_path = DATA_DIR / "audio" / f"{episode_id}.mp3"
    audio_processor.stitch_episode(segment_paths, output_path)
    logger.info("VoiceAgent: episode assembled at %s", output_path)
    return output_path
