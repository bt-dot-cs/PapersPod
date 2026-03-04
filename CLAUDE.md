# PapersPod — Agent Project Bible

Read this file completely before touching any code. It governs all agent behavior in this project.

---

## What This Project Is

PapersPod is an automated research-to-podcast pipeline:

1. User sets query parameters (topic, disciplines, expertise level, date ranges)
2. `FetcherAgent` queries arXiv + Semantic Scholar and returns enriched paper metadata
3. `BibliographyAgent` generates annotated bibliography drafts via Claude, adapted to user expertise
4. `GraphAgent` extracts entities/relationships and updates the persistent NetworkX knowledge graph
5. `ScriptAgent` generates a two-host dialogue podcast script (Host A: expert explainer, Host B: curious generalist)
6. `VoiceAgent` sends each dialogue turn to ElevenLabs (two voices), stitches audio with pydub
7. Output: MP3 + annotated bibliography + updated knowledge graph

Full plan is in `PapersPod_Plan.md`. Read Section 3 (Plan) for data models, architecture, and phase details.

---

## Module Ownership

Each agent owns specific files. **Do not modify files outside your module's scope.**

| Module | Owned Files |
|---|---|
| `orchestrator` | `agents/orchestrator.py`, `core/models.py`, `core/config.py` |
| `fetcher` | `agents/fetcher_agent.py`, `core/arxiv_client.py`, `core/semantic_scholar_client.py`, `tests/unit/test_arxiv_client.py`, `tests/unit/test_semantic_scholar_client.py` |
| `bibliography` | `agents/bibliography_agent.py`, `tests/unit/test_bibliography_agent.py` |
| `graph` | `agents/graph_agent.py`, `core/knowledge_graph.py`, `tests/unit/test_knowledge_graph.py` |
| `script` | `agents/script_agent.py`, `tests/unit/test_script_agent.py` |
| `voice` | `agents/voice_agent.py`, `core/audio_processor.py`, `tests/unit/test_voice_agent.py`, `tests/unit/test_audio_processor.py` |
| `web` | `web/`, `tests/integration/test_api.py` |

---

## Tech Stack

- **Python 3.11+**
- **Pydantic v2** for all data models (use `model_validator`, `field_validator` v2 syntax)
- **`arxiv` Python package** (not raw HTTP) for arXiv queries
- **`semanticscholar` SDK** for Semantic Scholar queries
- **`anthropic` SDK** — use `claude-sonnet-4-6` model for all Claude calls
- **`networkx`** for knowledge graph operations
- **`pydub`** for audio stitching; requires `ffmpeg` installed system-level
- **`elevenlabs`** SDK for TTS
- **`fastapi`** + `uvicorn` for web layer
- **`pytest`** + `pytest-asyncio` for all tests
- **`respx`** for mocking HTTP calls in tests (never make real API calls in unit tests)
- **`python-dotenv`** for loading `.env`

---

## Coding Conventions

### General
- Type hints on every function signature (parameters and return types)
- Docstrings on public functions — one line description, no novels
- No hardcoded strings for API keys, voice IDs, model names — all from `core/config.py`
- Prefer `async def` for I/O-bound operations (API calls, file writes)
- Use `pathlib.Path` for all file paths, not `os.path`
- Log at `INFO` level for normal operations, `ERROR` for failures — use Python's `logging` module

### Data Models (`core/models.py`)
- All models inherit from `pydantic.BaseModel`
- Use `Optional[X]` with explicit `None` defaults for nullable fields
- `Paper.arxiv_id` is the canonical deduplication key
- `Concept` normalized string = lowercase, stripped, replace spaces with underscores

### Knowledge Graph (`core/knowledge_graph.py`)
- Graph is append-only — never delete nodes or edges
- Every node has `node_type` attribute matching its model name
- Every node has `first_seen_date` (ISO string) set on creation
- Serialize to `data/graphs/graph.graphml` after every modification
- Also maintain `data/graphs/graph_snapshot.json` (D3-compatible format) after every modification

### Audio (`core/audio_processor.py`)
- Each dialogue turn is a separate MP3 segment in `data/audio/segments/{episode_id}/`
- Silence between turns: 400ms
- Final assembled episode: `data/audio/{episode_id}.mp3`
- Always export at 128kbps MP3

### Agent Output Files
- Papers: `data/papers/{episode_id}.json`
- Bibliography: `data/bibliographies/{episode_id}.md`
- Script: `data/scripts/{episode_id}.json` (structured turns) + `{episode_id}.md` (human-readable)
- Audio: `data/audio/{episode_id}.mp3`

### Episode IDs
Format: `{YYYY-MM-DD}_{slugified-topic}_{4-char-hex}` e.g. `2026-03-03_transformer-architectures_a3f1`

---

## Environment

API keys are in `.env` (never commit this file). Load with:
```python
from dotenv import load_dotenv
load_dotenv()
```

Required keys:
```
ANTHROPIC_API_KEY
ELEVENLABS_API_KEY
ELEVENLABS_VOICE_A_ID    # Host A (expert explainer)
ELEVENLABS_VOICE_B_ID    # Host B (curious generalist)
```

Optional:
```
SEMANTIC_SCHOLAR_API_KEY  # Increases S2 rate limits; works without it
```

---

## Running Tests

```bash
# Unit tests only (no API calls, always safe to run)
pytest tests/unit/ -v

# Integration tests (requires real API keys in .env)
pytest tests/integration/ -v

# Specific module
pytest tests/unit/test_arxiv_client.py -v
```

All unit tests must pass with no real API calls. Use `respx` to mock HTTP. Use `unittest.mock.patch` or `pytest-mock` for SDK calls.

---

## Commit Conventions

One commit per completed module. Message format:
```
feat(module): brief description

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

Examples:
```
feat(core): add Paper and QueryParameters Pydantic models
feat(fetcher): arxiv + semantic scholar client with expertise-level filtering
test(fetcher): unit tests for arxiv_client and semantic_scholar_client
feat(graph): NetworkX knowledge graph with append-only operations
```

---

## Agent Rules

1. **Read this file and `PapersPod_Plan.md` Section 3 before writing any code**
2. **Only touch files in your module's ownership scope** (see Module Ownership table above)
3. **Run unit tests before marking your task complete** — `pytest tests/unit/` must pass
4. **Never hardcode API keys, voice IDs, or model names** — use `core/config.py`
5. **Never make real API calls in unit tests** — mock everything with `respx` or `unittest.mock`
6. **Commit when your module is complete and tests pass**
7. **If a dependency module is incomplete, stub it** — don't block on other agents
8. **Do not refactor or improve code in other modules** — raise a note and move on

---

## Definition of Done (Phase 1)

Phase 1 is complete when:
- [ ] `pytest tests/unit/` passes with 0 failures
- [ ] `python -m agents.orchestrator --topic "attention mechanisms" --disciplines "machine learning" --focus-mode depth --publication-start 2022-01-01 --publication-end 2026-01-01 --max-papers 3` runs end-to-end
- [ ] `data/audio/{episode_id}.mp3` exists and is a valid audio file
- [ ] `data/graphs/graph.graphml` exists and has at least 5 nodes
- [ ] `data/bibliographies/{episode_id}.md` exists and references each paper
- [ ] All output committed to local git with module-level commits
