import asyncio
import logging
from functools import partial

logger = logging.getLogger(__name__)


def _synthesize_sync(text: str, voice_name: str) -> bytes:
    """Synchronous Google Cloud TTS call (wrapped for async use)."""
    from google.cloud import texttospeech  # type: ignore

    client = texttospeech.TextToSpeechClient()
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        name=voice_name,
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=1.0,
    )
    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config,
    )
    return response.audio_content


async def synthesize(text: str, voice_id: str) -> bytes:
    """Synthesize text via Google Cloud Text-to-Speech.

    voice_id should be a Neural2 or WaveNet voice name, e.g.:
      - en-US-Neural2-F  (female, Host A)
      - en-US-Neural2-D  (male, Host B)

    Requires GOOGLE_APPLICATION_CREDENTIALS env var pointing to a
    service account JSON key file, or Application Default Credentials.
    Free tier: 1M characters/month for Neural2 voices.
    """
    loop = asyncio.get_event_loop()
    try:
        audio_bytes = await loop.run_in_executor(
            None, partial(_synthesize_sync, text, voice_id)
        )
        logger.debug("Google TTS: synthesized %d chars → %d bytes", len(text), len(audio_bytes))
        return audio_bytes
    except ImportError:
        raise ImportError(
            "google-cloud-texttospeech is required for VOICE_PROVIDER=google. "
            "Install it with: pip install google-cloud-texttospeech"
        )
