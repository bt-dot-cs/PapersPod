import logging
from pathlib import Path

from pydub import AudioSegment

logger = logging.getLogger(__name__)

_EXPORT_BITRATE = "128k"


def normalize_audio(audio_segment: AudioSegment, target_dbfs: float = -20.0) -> AudioSegment:
    """Normalize audio level to target dBFS."""
    delta = target_dbfs - audio_segment.dBFS
    return audio_segment.apply_gain(delta)


def stitch_episode(
    segment_paths: list[Path],
    output_path: Path,
    silence_between_ms: int = 400,
) -> tuple[Path, list[tuple[float, float]]]:
    """Concatenate MP3 segments with silence between each, export as 128kbps MP3.

    Returns (output_path, timings) where timings[i] = (start_seconds, end_seconds).
    """
    if not segment_paths:
        raise ValueError("segment_paths must not be empty")

    silence = AudioSegment.silent(duration=silence_between_ms)
    combined = AudioSegment.empty()
    timings: list[tuple[float, float]] = []

    for i, path in enumerate(segment_paths):
        segment = AudioSegment.from_mp3(path)
        segment = normalize_audio(segment)
        if i > 0:
            combined += silence
        start_ms = len(combined)
        combined += segment
        timings.append((start_ms / 1000, len(combined) / 1000))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.export(output_path, format="mp3", bitrate=_EXPORT_BITRATE)
    logger.info("Episode assembled: %s (%.1fs)", output_path, len(combined) / 1000)
    return output_path, timings
