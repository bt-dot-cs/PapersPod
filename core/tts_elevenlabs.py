import asyncio
import logging

from elevenlabs.client import ElevenLabs

from core.config import ELEVENLABS_API_KEY

logger = logging.getLogger(__name__)

_RATE_LIMIT_RETRY_SECONDS = 5


def _client() -> ElevenLabs:
    if not ELEVENLABS_API_KEY:
        raise ValueError("ELEVENLABS_API_KEY is required when VOICE_PROVIDER=elevenlabs")
    return ElevenLabs(api_key=ELEVENLABS_API_KEY)


async def synthesize(text: str, voice_id: str) -> bytes:
    """Synthesize text via ElevenLabs TTS; retry once on 429 rate limit."""
    client = _client()
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
                logger.warning("ElevenLabs: rate limited (429), retrying in %ds", _RATE_LIMIT_RETRY_SECONDS)
                await asyncio.sleep(_RATE_LIMIT_RETRY_SECONDS)
                continue
            raise
    raise RuntimeError("ElevenLabs TTS request failed after retry")
