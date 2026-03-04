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
ELEVENLABS_API_KEY: str = _require("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_A_ID: str = _require("ELEVENLABS_VOICE_A_ID")
ELEVENLABS_VOICE_B_ID: str = _require("ELEVENLABS_VOICE_B_ID")
SEMANTIC_SCHOLAR_API_KEY: str | None = os.getenv("SEMANTIC_SCHOLAR_API_KEY") or None

CLAUDE_MODEL: str = "claude-sonnet-4-6"

DATA_DIR: Path = Path("data")
GRAPH_PATH: Path = DATA_DIR / "graphs" / "graph.graphml"
GRAPH_SNAPSHOT_PATH: Path = DATA_DIR / "graphs" / "graph_snapshot.json"

ARXIV_RATE_LIMIT_SECONDS: float = 3.0
