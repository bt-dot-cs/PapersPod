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

# Product mode gate — controls license filtering, disclaimer injection, and attribution enforcement
PRODUCT_MODE: str = os.getenv("PRODUCT_MODE", "personal")
if PRODUCT_MODE not in ("personal", "commercial"):
    raise ValueError(
        f"PRODUCT_MODE must be 'personal' or 'commercial', got '{PRODUCT_MODE}'. "
        "Check your .env file."
    )
COMMERCIAL_MODE: bool = PRODUCT_MODE == "commercial"

# Voice provider selection
VOICE_PROVIDER: str = os.getenv("VOICE_PROVIDER", "openai")  # openai | elevenlabs | google

# ElevenLabs (required when VOICE_PROVIDER=elevenlabs or elevenlabs_free)
ELEVENLABS_API_KEY: str | None = os.getenv("ELEVENLABS_API_KEY") or None
ELEVENLABS_VOICE_A_ID: str = os.getenv("ELEVENLABS_VOICE_A_ID", "")        # premium library voice
ELEVENLABS_VOICE_B_ID: str = os.getenv("ELEVENLABS_VOICE_B_ID", "")        # premium library voice
ELEVENLABS_VOICE_A_FREE_ID: str = os.getenv("ELEVENLABS_VOICE_A_FREE_ID", "XrExE9yKIg1WjnnlVkGX")  # Matilda — premade
ELEVENLABS_VOICE_B_FREE_ID: str = os.getenv("ELEVENLABS_VOICE_B_FREE_ID", "SAz9YHcvj6GT2YYXdXww")  # River — premade

# OpenAI TTS (required when VOICE_PROVIDER=openai)
OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY") or None
OPENAI_TTS_VOICE_A: str = os.getenv("OPENAI_TTS_VOICE_A", "nova")   # female-leaning
OPENAI_TTS_VOICE_B: str = os.getenv("OPENAI_TTS_VOICE_B", "onyx")   # male-leaning

# Google Cloud TTS (required when VOICE_PROVIDER=google; set GOOGLE_APPLICATION_CREDENTIALS)
GOOGLE_TTS_VOICE_A: str = os.getenv("GOOGLE_TTS_VOICE_A", "en-US-Neural2-F")
GOOGLE_TTS_VOICE_B: str = os.getenv("GOOGLE_TTS_VOICE_B", "en-US-Neural2-D")

SEMANTIC_SCHOLAR_API_KEY: str | None = os.getenv("SEMANTIC_SCHOLAR_API_KEY") or None
OPENALEX_EMAIL: str = os.getenv("OPENALEX_EMAIL", "")
SPRINGER_API_KEY: str | None = os.getenv("SPRINGER_API_KEY") or None
IEEE_API_KEY: str | None = os.getenv("IEEE_API_KEY") or None

CLAUDE_MODEL: str = "claude-sonnet-4-6"
CLAUDE_HAIKU_MODEL: str = "claude-haiku-4-5-20251001"

# Absolute path — resolved relative to this file so output lands in the project
# regardless of the shell's working directory when the pipeline is invoked.
_PROJECT_ROOT: Path = Path(__file__).parent.parent
DATA_DIR: Path = _PROJECT_ROOT / "data"
GRAPH_PATH: Path = DATA_DIR / "graphs" / "graph.graphml"
GRAPH_SNAPSHOT_PATH: Path = DATA_DIR / "graphs" / "graph_snapshot.json"

ARXIV_RATE_LIMIT_SECONDS: float = 3.0
OPENALEX_RATE_LIMIT_SECONDS: float = 0.1

# Pricing constants (USD per token / character)
# claude-sonnet-4-6 standard rates
CLAUDE_INPUT_COST_PER_M_TOKENS: float = 3.00
CLAUDE_OUTPUT_COST_PER_M_TOKENS: float = 15.00
# TTS rates per 1M characters
TTS_COST_PER_M_CHARS: dict[str, float] = {
    "openai": 15.00,           # tts-1
    "google": 16.00,           # Neural2
    "elevenlabs": 300.00,      # PAYG rate; subscription plans vary
    "elevenlabs_free": 300.00, # same API as elevenlabs; premade voices, free-tier accessible
}
