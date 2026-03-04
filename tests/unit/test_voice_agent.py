import math
import struct
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydub import AudioSegment

from core.models import DialogueTurn, PodcastScript


def _make_script(n_turns: int = 4) -> PodcastScript:
    turns = []
    for i in range(n_turns):
        turns.append(DialogueTurn(host="A" if i % 2 == 0 else "B", text=f"Turn {i} text."))
    return PodcastScript(
        episode_id="2026-03-04_test_ab12",
        title="Test Episode",
        turns=turns,
        paper_ids=["2301.12345"],
    )


def _make_mp3_bytes(duration_ms: int = 200) -> bytes:
    """Generate a tiny valid MP3 as bytes using pydub (uses real ffmpeg)."""
    sample_rate = 44100
    num_samples = int(sample_rate * duration_ms / 1000)
    raw = b"".join(
        struct.pack("<h", int(16383 * math.sin(2 * math.pi * 440 * i / sample_rate)))
        for i in range(num_samples)
    )
    seg = AudioSegment(data=raw, sample_width=2, frame_rate=sample_rate, channels=1)
    import io
    buf = io.BytesIO()
    seg.export(buf, format="mp3", bitrate="128k")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_voice_agent_generates_segments(tmp_path: Path):
    """All turns generate segment files at the correct paths."""
    script = _make_script(n_turns=2)
    mp3_bytes = _make_mp3_bytes()

    with patch("agents.voice_agent.ElevenLabs") as MockEL, \
         patch("agents.voice_agent.DATA_DIR", tmp_path):
        MockEL.return_value.text_to_speech.convert.side_effect = \
            lambda voice_id, text, model_id: iter([mp3_bytes])
        from agents.voice_agent import run
        result = await run(script)

    seg_dir = tmp_path / "audio" / "segments" / script.episode_id
    assert (seg_dir / "000_A.mp3").exists()
    assert (seg_dir / "001_B.mp3").exists()


@pytest.mark.asyncio
async def test_voice_agent_returns_episode_path(tmp_path: Path):
    """run() returns the path to the assembled episode MP3."""
    script = _make_script(n_turns=2)
    mp3_bytes = _make_mp3_bytes()

    with patch("agents.voice_agent.ElevenLabs") as MockEL, \
         patch("agents.voice_agent.DATA_DIR", tmp_path):
        MockEL.return_value.text_to_speech.convert.side_effect = \
            lambda voice_id, text, model_id: iter([mp3_bytes])
        from agents.voice_agent import run
        result = await run(script)

    expected = tmp_path / "audio" / f"{script.episode_id}.mp3"
    assert result == expected
    assert result.exists()


@pytest.mark.asyncio
async def test_voice_agent_correct_voice_per_host(tmp_path: Path):
    """Host A uses VOICE_A_ID, Host B uses VOICE_B_ID."""
    script = _make_script(n_turns=2)
    mp3_bytes = _make_mp3_bytes()
    captured_voice_ids = []

    def mock_convert(voice_id, text, model_id):
        captured_voice_ids.append(voice_id)
        return iter([mp3_bytes])

    with patch("agents.voice_agent.ElevenLabs") as MockEL, \
         patch("agents.voice_agent.DATA_DIR", tmp_path), \
         patch("agents.voice_agent.ELEVENLABS_VOICE_A_ID", "voice-a-id"), \
         patch("agents.voice_agent.ELEVENLABS_VOICE_B_ID", "voice-b-id"):
        MockEL.return_value.text_to_speech.convert.side_effect = mock_convert
        from agents.voice_agent import run
        await run(script)

    assert captured_voice_ids[0] == "voice-a-id"   # Turn 0 is host A
    assert captured_voice_ids[1] == "voice-b-id"   # Turn 1 is host B


@pytest.mark.asyncio
async def test_voice_agent_segments_in_order(tmp_path: Path):
    """stitch_episode receives segment paths in the correct order."""
    script = _make_script(n_turns=3)
    mp3_bytes = _make_mp3_bytes()

    captured_paths = []

    def mock_stitch(segment_paths, output_path, silence_between_ms=400):
        captured_paths.extend(segment_paths)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(mp3_bytes)
        return output_path

    with patch("agents.voice_agent.ElevenLabs") as MockEL, \
         patch("agents.voice_agent.DATA_DIR", tmp_path), \
         patch("agents.voice_agent.audio_processor.stitch_episode", side_effect=mock_stitch):
        MockEL.return_value.text_to_speech.convert.return_value = iter([mp3_bytes])
        from agents.voice_agent import run
        await run(script)

    assert len(captured_paths) == 3
    assert "000_A" in str(captured_paths[0])
    assert "001_B" in str(captured_paths[1])
    assert "002_A" in str(captured_paths[2])


@pytest.mark.asyncio
async def test_voice_agent_429_retry(tmp_path: Path):
    """On 429 error, agent retries once after sleep."""
    script = _make_script(n_turns=1)
    mp3_bytes = _make_mp3_bytes()
    call_count = 0

    def mock_convert(voice_id, text, model_id):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("429 Too Many Requests")
        return iter([mp3_bytes])

    with patch("agents.voice_agent.ElevenLabs") as MockEL, \
         patch("agents.voice_agent.DATA_DIR", tmp_path), \
         patch("agents.voice_agent.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        MockEL.return_value.text_to_speech.convert.side_effect = mock_convert
        from agents.voice_agent import run
        result = await run(script)

    assert call_count == 2
    mock_sleep.assert_called_once()
