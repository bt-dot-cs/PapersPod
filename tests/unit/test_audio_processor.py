import math
import struct
from pathlib import Path

import pytest
from pydub import AudioSegment

from core.audio_processor import normalize_audio, stitch_episode


def _make_tone(frequency: int = 440, duration_ms: int = 500) -> AudioSegment:
    """Generate a sine wave AudioSegment (non-silent, has real dBFS)."""
    sample_rate = 44100
    num_samples = int(sample_rate * duration_ms / 1000)
    raw = b"".join(
        struct.pack("<h", int(16383 * math.sin(2 * math.pi * frequency * i / sample_rate)))
        for i in range(num_samples)
    )
    return AudioSegment(data=raw, sample_width=2, frame_rate=sample_rate, channels=1)


def _make_segment_file(tmp_path: Path, name: str, duration_ms: int = 500) -> Path:
    """Create a real MP3 file with a silent audio segment of given duration."""
    seg = AudioSegment.silent(duration=duration_ms)
    path = tmp_path / name
    seg.export(path, format="mp3", bitrate="128k")
    return path


# --- normalize_audio ---

def test_normalize_audio_adjusts_level():
    """Normalized segment should be at approximately the target dBFS."""
    seg = _make_tone(duration_ms=500)  # Real tone with finite dBFS
    target = -20.0
    normalized = normalize_audio(seg, target_dbfs=target)
    assert abs(normalized.dBFS - target) < 1.0


def test_normalize_audio_returns_audio_segment():
    seg = AudioSegment.silent(duration=500)
    result = normalize_audio(seg)
    assert isinstance(result, AudioSegment)


# --- stitch_episode ---

def test_stitch_episode_output_exists(tmp_path: Path):
    """Stitched output file exists at the specified path."""
    seg1 = _make_segment_file(tmp_path, "seg1.mp3", 300)
    seg2 = _make_segment_file(tmp_path, "seg2.mp3", 300)
    output = tmp_path / "output" / "episode.mp3"

    result_path, timings = stitch_episode([seg1, seg2], output)

    assert result_path == output
    assert output.exists()
    assert len(timings) == 2


def test_stitch_episode_longer_than_inputs(tmp_path: Path):
    """Output is longer than each individual segment (because silence is added)."""
    seg1 = _make_segment_file(tmp_path, "seg1.mp3", 500)
    seg2 = _make_segment_file(tmp_path, "seg2.mp3", 500)
    output = tmp_path / "episode.mp3"

    stitch_episode([seg1, seg2], output, silence_between_ms=400)

    result_audio = AudioSegment.from_mp3(output)
    # Total >= 500 + 400 + 500 = 1400ms (with some MP3 encoding tolerance)
    assert len(result_audio) >= 1300


def test_stitch_episode_single_segment(tmp_path: Path):
    """Single segment produces a valid output file."""
    seg1 = _make_segment_file(tmp_path, "seg1.mp3", 600)
    output = tmp_path / "episode.mp3"

    stitch_episode([seg1], output)

    assert output.exists()
    result_audio = AudioSegment.from_mp3(output)
    assert len(result_audio) > 0


def test_stitch_episode_creates_parent_dirs(tmp_path: Path):
    """Parent directories are created if they don't exist."""
    seg1 = _make_segment_file(tmp_path, "seg1.mp3", 300)
    output = tmp_path / "nested" / "deep" / "episode.mp3"

    stitch_episode([seg1], output)

    assert output.exists()


def test_stitch_episode_empty_list_raises(tmp_path: Path):
    """Empty segment list raises ValueError."""
    with pytest.raises(ValueError, match="must not be empty"):
        stitch_episode([], tmp_path / "episode.mp3")


def test_stitch_episode_three_segments_silence_count(tmp_path: Path):
    """Three segments get two silence gaps inserted."""
    segs = [_make_segment_file(tmp_path, f"seg{i}.mp3", 200) for i in range(3)]
    output = tmp_path / "episode.mp3"
    silence_ms = 500

    stitch_episode(segs, output, silence_between_ms=silence_ms)

    result = AudioSegment.from_mp3(output)
    # 3 × 200ms segments + 2 × 500ms silence = 1600ms minimum
    assert len(result) >= 1500
