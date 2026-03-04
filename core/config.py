import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _require(key: str) -> str:
    """Return env var value or raise a clear ValueError."""
    value = os.getenv(key)
    if not value:
        raise ValueError(
            f"Required environment variable '{key}' is not set. "
            "Copy .env.example to .env and fill in your API keys."
        )
    return value


ANTHROPIC_API_KEY: str = _require("ANTHROPIC_API_KEY")

# Voice provider selection
VOICE_PROVIDER: str = os.getenv("VOICE_PROVIDER", "elevenlabs")  # elevenlabs | openai | google

# ElevenLabs (required when VOICE_PROVIDER=elevenlabs)
ELEVENLABS_API_KEY: str | None = os.getenv("ELEVENLABS_API_KEY") or None
ELEVENLABS_VOICE_A_ID: str = os.getenv("ELEVENLABS_VOICE_A_ID", "")
ELEVENLABS_VOICE_B_ID: str = os.getenv("ELEVENLABS_VOICE_B_ID", "")

# OpenAI TTS (required when VOICE_PROVIDER=openai)
OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY") or None
OPENAI_TTS_VOICE_A: str = os.getenv("OPENAI_TTS_VOICE_A", "nova")   # female-leaning
OPENAI_TTS_VOICE_B: str = os.getenv("OPENAI_TTS_VOICE_B", "onyx")   # male-leaning

# Google Cloud TTS (required when VOICE_PROVIDER=google; set GOOGLE_APPLICATION_CREDENTIALS)
GOOGLE_TTS_VOICE_A: str = os.getenv("GOOGLE_TTS_VOICE_A", "en-US-Neural2-F")
GOOGLE_TTS_VOICE_B: str = os.getenv("GOOGLE_TTS_VOICE_B", "en-US-Neural2-D")

SEMANTIC_SCHOLAR_API_KEY: str | None = os.getenv("SEMANTIC_SCHOLAR_API_KEY") or None
OPENALEX_EMAIL: str = os.getenv("OPENALEX_EMAIL", "")

CLAUDE_MODEL: str = "claude-sonnet-4-6"

DATA_DIR: Path = Path("data")
GRAPH_PATH: Path = DATA_DIR / "graphs" / "graph.graphml"
GRAPH_SNAPSHOT_PATH: Path = DATA_DIR / "graphs" / "graph_snapshot.json"

ARXIV_RATE_LIMIT_SECONDS: float = 3.0
OPENALEX_RATE_LIMIT_SECONDS: float = 0.1
