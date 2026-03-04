import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# --- ElevenLabs ---

@pytest.mark.asyncio
async def test_elevenlabs_synthesize_returns_bytes():
    """synthesize() concatenates the generator chunks into bytes."""
    mp3_chunk = b"\xff\xfb\x90\x00" * 100

    with patch("core.tts_elevenlabs.ELEVENLABS_API_KEY", "test-key"), \
         patch("core.tts_elevenlabs.ElevenLabs") as MockEL:
        MockEL.return_value.text_to_speech.convert.return_value = iter([mp3_chunk])
        from core.tts_elevenlabs import synthesize
        result = await synthesize("Hello world", "voice-abc")

    assert result == mp3_chunk
    MockEL.return_value.text_to_speech.convert.assert_called_once_with(
        voice_id="voice-abc", text="Hello world", model_id="eleven_multilingual_v2"
    )


@pytest.mark.asyncio
async def test_elevenlabs_429_retry():
    """On 429, synthesize retries once after sleep."""
    mp3_chunk = b"\xff\xfb\x90\x00" * 100
    call_count = 0

    def mock_convert(voice_id, text, model_id):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("429 Too Many Requests")
        return iter([mp3_chunk])

    with patch("core.tts_elevenlabs.ELEVENLABS_API_KEY", "test-key"), \
         patch("core.tts_elevenlabs.ElevenLabs") as MockEL, \
         patch("core.tts_elevenlabs.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        MockEL.return_value.text_to_speech.convert.side_effect = mock_convert
        from core.tts_elevenlabs import synthesize
        result = await synthesize("Hello", "voice-abc")

    assert call_count == 2
    mock_sleep.assert_called_once()
    assert result == mp3_chunk


@pytest.mark.asyncio
async def test_elevenlabs_non_429_raises():
    """Non-429 errors are re-raised immediately without retry."""
    with patch("core.tts_elevenlabs.ELEVENLABS_API_KEY", "test-key"), \
         patch("core.tts_elevenlabs.ElevenLabs") as MockEL:
        MockEL.return_value.text_to_speech.convert.side_effect = RuntimeError("500 Server Error")
        from core.tts_elevenlabs import synthesize
        with pytest.raises(RuntimeError, match="500 Server Error"):
            await synthesize("Hello", "voice-abc")


@pytest.mark.asyncio
async def test_elevenlabs_missing_key_raises():
    """Missing API key raises ValueError before making any API call."""
    with patch("core.tts_elevenlabs.ELEVENLABS_API_KEY", None):
        from core.tts_elevenlabs import synthesize
        with pytest.raises(ValueError, match="ELEVENLABS_API_KEY"):
            await synthesize("Hello", "voice-abc")


# --- OpenAI ---

@pytest.mark.asyncio
async def test_openai_synthesize_returns_bytes():
    """synthesize() returns response.content bytes."""
    mp3_bytes = b"\xff\xfb\x90\x00" * 100
    mock_response = MagicMock()
    mock_response.content = mp3_bytes

    with patch("core.tts_openai.OPENAI_API_KEY", "sk-test"), \
         patch("core.tts_openai.OpenAI") as MockOAI:
        MockOAI.return_value.audio.speech.create.return_value = mock_response
        from core.tts_openai import synthesize
        result = await synthesize("Hello world", "nova")

    assert result == mp3_bytes
    MockOAI.return_value.audio.speech.create.assert_called_once_with(
        model="tts-1", voice="nova", input="Hello world", response_format="mp3"
    )


@pytest.mark.asyncio
async def test_openai_missing_key_raises():
    """Missing API key raises ValueError."""
    with patch("core.tts_openai.OPENAI_API_KEY", None):
        from core.tts_openai import synthesize
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            await synthesize("Hello", "nova")


# --- Google ---

@pytest.mark.asyncio
async def test_google_synthesize_returns_bytes():
    """synthesize() runs _synthesize_sync in executor and returns bytes."""
    mp3_bytes = b"\xff\xfb\x90\x00" * 100

    with patch("core.tts_google._synthesize_sync", return_value=mp3_bytes) as mock_sync:
        from core.tts_google import synthesize
        result = await synthesize("Hello world", "en-US-Neural2-F")

    assert result == mp3_bytes
    mock_sync.assert_called_once_with("Hello world", "en-US-Neural2-F")
