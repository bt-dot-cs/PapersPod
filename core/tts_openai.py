import logging

from openai import OpenAI

from core.config import OPENAI_API_KEY

logger = logging.getLogger(__name__)


def _client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is required when VOICE_PROVIDER=openai")
    return OpenAI(api_key=OPENAI_API_KEY)


async def synthesize(text: str, voice_id: str) -> bytes:
    """Synthesize text via OpenAI TTS API.

    voice_id should be one of: alloy, echo, fable, onyx, nova, shimmer.
    Uses tts-1 model (lower latency, suitable for podcast generation).
    """
    client = _client()
    response = client.audio.speech.create(
        model="tts-1",
        voice=voice_id,
        input=text,
        response_format="mp3",
    )
    audio_bytes = response.content
    logger.debug("OpenAI TTS: synthesized %d chars → %d bytes", len(text), len(audio_bytes))
    return audio_bytes
