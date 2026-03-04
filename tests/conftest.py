import os

# Set fake API keys at module level so they're in place before any test file
# imports core.config (which validates these at import time).
# Uses setdefault so real shell env vars / real .env values are not overridden.
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-anthropic-xxxx")
os.environ.setdefault("ELEVENLABS_API_KEY", "sk-test-elevenlabs-xxxx")
os.environ.setdefault("ELEVENLABS_VOICE_A_ID", "test-voice-a-xxxx")
os.environ.setdefault("ELEVENLABS_VOICE_B_ID", "test-voice-b-xxxx")
