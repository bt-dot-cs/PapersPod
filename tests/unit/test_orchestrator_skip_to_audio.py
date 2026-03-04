import json
import math
import struct
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pydub import AudioSegment

from core.models import DialogueTurn, PodcastScript


def _make_script(episode_id: str = "2026-03-04_test_ab12") -> PodcastScript:
    return PodcastScript(
        episode_id=episode_id,
        title="Test Episode",
        turns=[
            DialogueTurn(host="A", text="Hello from host A."),
            DialogueTurn(host="B", text="Hello from host B."),
        ],
        paper_ids=["2301.12345"],
    )


def _make_mp3_bytes() -> bytes:
    sample_rate = 44100
    num_samples = int(sample_rate * 0.1)
    raw = b"".join(
        struct.pack("<h", int(16383 * math.sin(2 * math.pi * 440 * i / sample_rate)))
        for i in range(num_samples)
    )
    import io
    seg = AudioSegment(data=raw, sample_width=2, frame_rate=sample_rate, channels=1)
    buf = io.BytesIO()
    seg.export(buf, format="mp3", bitrate="128k")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_run_audio_only_loads_script_and_calls_voice_agent(tmp_path: Path):
    """run_audio_only loads the saved JSON script and passes it to voice_agent.run."""
    episode_id = "2026-03-04_test_ab12"
    script = _make_script(episode_id)
    mp3_bytes = _make_mp3_bytes()

    # Write a real script JSON to tmp_path/scripts/
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True)
    script_file = scripts_dir / f"{episode_id}.json"
    script_file.write_text(script.model_dump_json())

    expected_audio = tmp_path / "audio" / f"{episode_id}.mp3"

    async def fake_voice_run(loaded_script: PodcastScript) -> Path:
        assert loaded_script.episode_id == episode_id
        assert len(loaded_script.turns) == 2
        expected_audio.parent.mkdir(parents=True, exist_ok=True)
        expected_audio.write_bytes(mp3_bytes)
        return expected_audio

    with patch("agents.orchestrator.DATA_DIR", tmp_path), \
         patch("agents.voice_agent.DATA_DIR", tmp_path), \
         patch("agents.voice_agent._synthesize", new_callable=AsyncMock, return_value=mp3_bytes):
        from agents.orchestrator import run_audio_only
        result = await run_audio_only(episode_id)

    assert result == expected_audio


@pytest.mark.asyncio
async def test_run_audio_only_raises_if_script_missing(tmp_path: Path):
    """run_audio_only raises FileNotFoundError when no script exists for the episode."""
    with patch("agents.orchestrator.DATA_DIR", tmp_path):
        from agents.orchestrator import run_audio_only
        with pytest.raises(FileNotFoundError, match="No saved script"):
            await run_audio_only("nonexistent-episode-id")


@pytest.mark.asyncio
async def test_run_audio_only_overrides_voice_provider(tmp_path: Path):
    """--voice-provider sets voice_agent.VOICE_PROVIDER before synthesis runs."""
    import agents.voice_agent as va

    episode_id = "2026-03-04_test_ab12"
    script = _make_script(episode_id)
    mp3_bytes = _make_mp3_bytes()

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / f"{episode_id}.json").write_text(script.model_dump_json())

    captured_provider = []

    async def fake_synthesize(text: str, host: str) -> bytes:
        captured_provider.append(va.VOICE_PROVIDER)
        return mp3_bytes

    with patch("agents.orchestrator.DATA_DIR", tmp_path), \
         patch("agents.voice_agent.DATA_DIR", tmp_path), \
         patch("agents.voice_agent._synthesize", side_effect=fake_synthesize):
        from agents.orchestrator import run_audio_only
        await run_audio_only(episode_id, voice_provider="openai")

    assert all(p == "openai" for p in captured_provider)
