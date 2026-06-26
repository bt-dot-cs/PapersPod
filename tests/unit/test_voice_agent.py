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

    with patch("agents.voice_agent._synthesize", new_callable=AsyncMock, return_value=mp3_bytes), \
         patch("agents.voice_agent.DATA_DIR", tmp_path), \
         patch("agents.voice_agent.shutil.rmtree"):
        from agents.voice_agent import run
        await run(script)

    seg_dir = tmp_path / "audio" / "segments" / script.episode_id
    assert (seg_dir / "000_A.mp3").exists()
    assert (seg_dir / "001_B.mp3").exists()


@pytest.mark.asyncio
async def test_voice_agent_returns_episode_path(tmp_path: Path):
    """run() returns the path to the assembled episode MP3."""
    script = _make_script(n_turns=2)
    mp3_bytes = _make_mp3_bytes()

    with patch("agents.voice_agent._synthesize", new_callable=AsyncMock, return_value=mp3_bytes), \
         patch("agents.voice_agent.DATA_DIR", tmp_path):
        from agents.voice_agent import run
        result_path, _chars, _provider, _segments = await run(script)

    expected = tmp_path / "audio" / f"{script.episode_id}.mp3"
    assert result_path == expected
    assert result_path.exists()


@pytest.mark.asyncio
async def test_voice_agent_correct_voice_per_host(tmp_path: Path):
    """_voice_id returns the right voice for each host under each provider."""
    import importlib
    import agents.voice_agent as va

    with patch("agents.voice_agent.ELEVENLABS_VOICE_A_ID", "el-voice-a"), \
         patch("agents.voice_agent.ELEVENLABS_VOICE_B_ID", "el-voice-b"):
        assert va._voice_id("A", "elevenlabs") == "el-voice-a"
        assert va._voice_id("B", "elevenlabs") == "el-voice-b"

    with patch("agents.voice_agent.OPENAI_TTS_VOICE_A", "nova"), \
         patch("agents.voice_agent.OPENAI_TTS_VOICE_B", "onyx"):
        assert va._voice_id("A", "openai") == "nova"
        assert va._voice_id("B", "openai") == "onyx"

    with patch("agents.voice_agent.GOOGLE_TTS_VOICE_A", "en-US-Neural2-F"), \
         patch("agents.voice_agent.GOOGLE_TTS_VOICE_B", "en-US-Neural2-D"):
        assert va._voice_id("A", "google") == "en-US-Neural2-F"
        assert va._voice_id("B", "google") == "en-US-Neural2-D"


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
        return output_path, [(0.0, 0.2)] * len(segment_paths)

    with patch("agents.voice_agent._synthesize", new_callable=AsyncMock, return_value=mp3_bytes), \
         patch("agents.voice_agent.DATA_DIR", tmp_path), \
         patch("agents.voice_agent.audio_processor.stitch_episode", side_effect=mock_stitch):
        from agents.voice_agent import run
        await run(script)

    assert len(captured_paths) == 3
    assert "000_A" in str(captured_paths[0])
    assert "001_B" in str(captured_paths[1])
    assert "002_A" in str(captured_paths[2])


@pytest.mark.asyncio
async def test_voice_agent_routes_to_openai(tmp_path: Path):
    """When VOICE_PROVIDER=openai, _synthesize calls tts_openai.synthesize."""
    script = _make_script(n_turns=1)
    mp3_bytes = _make_mp3_bytes()

    with patch("agents.voice_agent.VOICE_PROVIDER", "openai"), \
         patch("agents.voice_agent.tts_openai.synthesize", new_callable=AsyncMock, return_value=mp3_bytes) as mock_openai, \
         patch("agents.voice_agent.DATA_DIR", tmp_path):
        from agents.voice_agent import run
        await run(script)

    mock_openai.assert_called_once()


@pytest.mark.asyncio
async def test_voice_agent_routes_to_elevenlabs(tmp_path: Path):
    """When VOICE_PROVIDER=elevenlabs (default), _synthesize calls tts_elevenlabs.synthesize."""
    script = _make_script(n_turns=1)
    mp3_bytes = _make_mp3_bytes()

    with patch("agents.voice_agent.VOICE_PROVIDER", "elevenlabs"), \
         patch("agents.voice_agent.tts_elevenlabs.synthesize", new_callable=AsyncMock, return_value=mp3_bytes) as mock_el, \
         patch("agents.voice_agent.DATA_DIR", tmp_path):
        from agents.voice_agent import run
        await run(script)

    mock_el.assert_called_once()
