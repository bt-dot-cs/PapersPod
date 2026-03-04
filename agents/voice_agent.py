import asyncio
import logging
from pathlib import Path

from elevenlabs.client import ElevenLabs

from core import audio_processor
from core.config import DATA_DIR, ELEVENLABS_API_KEY, ELEVENLABS_VOICE_A_ID, ELEVENLABS_VOICE_B_ID
from core.models import PodcastScript

logger = logging.getLogger(__name__)

_RATE_LIMIT_RETRY_SECONDS = 5


async def run(script: PodcastScript) -> Path:
    """Generate audio for each dialogue turn via ElevenLabs, stitch into final MP3."""
    client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
    episode_id = script.episode_id

    segment_dir = DATA_DIR / "audio" / "segments" / episode_id
    segment_dir.mkdir(parents=True, exist_ok=True)

    segment_paths: list[Path] = []

    for idx, turn in enumerate(script.turns):
        voice_id = ELEVENLABS_VOICE_A_ID if turn.host == "A" else ELEVENLABS_VOICE_B_ID
        segment_path = segment_dir / f"{idx:03d}_{turn.host}.mp3"

        logger.info(
            "VoiceAgent: generating turn %d/%d (host=%s, chars=%d)",
            idx + 1, len(script.turns), turn.host, len(turn.text),
        )

        audio_bytes = await _generate_with_retry(client, voice_id, turn.text)
        segment_path.write_bytes(audio_bytes)
        turn.audio_segment_path = segment_path
        segment_paths.append(segment_path)

    output_path = DATA_DIR / "audio" / f"{episode_id}.mp3"
    audio_processor.stitch_episode(segment_paths, output_path)
    logger.info("VoiceAgent: episode assembled at %s", output_path)
    return output_path


async def _generate_with_retry(client: ElevenLabs, voice_id: str, text: str) -> bytes:
    """Call ElevenLabs TTS; retry once on 429 rate limit."""
    for attempt in range(2):
        try:
            audio_generator = client.text_to_speech.convert(
                voice_id=voice_id,
                text=text,
                model_id="eleven_multilingual_v2",
            )
            return b"".join(audio_generator)
        except Exception as exc:
            err_str = str(exc)
            if "429" in err_str and attempt == 0:
                logger.warning("VoiceAgent: rate limited (429), retrying in %ds", _RATE_LIMIT_RETRY_SECONDS)
                await asyncio.sleep(_RATE_LIMIT_RETRY_SECONDS)
                continue
            raise
    raise RuntimeError("VoiceAgent: ElevenLabs request failed after retry")
