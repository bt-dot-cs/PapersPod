# Phase 1 Task File — CLI Pipeline MVP

**Goal:** End-to-end run from CLI query parameters to MP3 + annotated bibliography + knowledge graph. No web UI.

**Before starting any task:** Read `CLAUDE.md` fully. Read `PapersPod_Plan.md` Section 3.

**Execution order:** Tasks must be completed in the numbered order below. Each task depends on the previous.

**Definition of done per task:** Code written, unit tests pass, committed to local git.

---

## Task 1 — Project Scaffold + Core Models

**Module:** `orchestrator`
**Files to create:**
- `core/models.py`
- `core/config.py`
- `requirements.txt`

### `core/models.py`
Implement all Pydantic v2 models:

```python
# Required models (implement all of these):

class ExpertiseLevel(str, Enum): novice, intermediate, expert

class ExpertiseProfile(BaseModel):
    discipline: str
    level: ExpertiseLevel

class UserProfile(BaseModel):
    expertise: list[ExpertiseProfile]
    default_level: ExpertiseLevel = ExpertiseLevel.intermediate

class QueryParameters(BaseModel):
    topic: str
    disciplines: list[str]
    cross_disciplinary: bool = False
    focus_mode: Literal["depth", "breadth"] = "breadth"
    publication_date_range: tuple[date, date]
    study_data_period: Optional[tuple[date, date]] = None
    max_papers: int = 10
    include_preprints: bool = True
    user_profile: Optional[UserProfile] = None

class Paper(BaseModel):
    arxiv_id: str                          # Canonical deduplication key
    title: str
    authors: list[str]
    abstract: str
    published_date: date
    study_period_start: Optional[date] = None   # Extracted from abstract
    study_period_end: Optional[date] = None
    pdf_url: Optional[str] = None
    # Semantic Scholar enrichment
    citation_count: Optional[int] = None
    citation_velocity: Optional[float] = None   # citations per year
    s2_tldr: Optional[str] = None
    # Graph state
    first_seen_date: Optional[date] = None
    # User ratings (populated post-episode)
    interest_score: Optional[int] = None        # 1–5
    depth_score: Optional[int] = None           # 1–5
    flagged_for_reading: bool = False

class DialogueTurn(BaseModel):
    host: Literal["A", "B"]
    text: str
    audio_segment_path: Optional[Path] = None   # Set by VoiceAgent

class PodcastScript(BaseModel):
    episode_id: str
    title: str
    turns: list[DialogueTurn]
    paper_ids: list[str]                        # arXiv IDs discussed

class Episode(BaseModel):
    episode_id: str
    query: QueryParameters
    papers: list[Paper]
    bibliography_path: Optional[Path] = None
    script_path: Optional[Path] = None
    audio_path: Optional[Path] = None
    graph_snapshot_path: Optional[Path] = None
    created_at: datetime

class PaperRating(BaseModel):
    paper_id: str
    episode_id: str
    interest_score: int     # 1–5
    depth_score: int        # 1–5
    flag_for_reading: bool = False
    notes: Optional[str] = None

class ReadingQueueItem(BaseModel):
    paper_id: str
    title: str
    added_date: date
    priority: int = 3       # 1–5, higher = more urgent
    status: Literal["queued", "reading", "done"] = "queued"
```

### `core/config.py`
Load all config from environment:

```python
# Load with python-dotenv
# Expose as module-level constants:
ANTHROPIC_API_KEY: str
ELEVENLABS_API_KEY: str
ELEVENLABS_VOICE_A_ID: str    # Host A — expert explainer
ELEVENLABS_VOICE_B_ID: str    # Host B — curious generalist
SEMANTIC_SCHOLAR_API_KEY: Optional[str]  # None if not set
CLAUDE_MODEL: str = "claude-sonnet-4-6"
DATA_DIR: Path = Path("data")
GRAPH_PATH: Path = DATA_DIR / "graphs" / "graph.graphml"
GRAPH_SNAPSHOT_PATH: Path = DATA_DIR / "graphs" / "graph_snapshot.json"
ARXIV_RATE_LIMIT_SECONDS: float = 3.0
```

Raise a clear `ValueError` on startup if `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_A_ID`, or `ELEVENLABS_VOICE_B_ID` are missing.

### `requirements.txt`
```
arxiv
semanticscholar
anthropic
pydantic>=2.0
python-dotenv
elevenlabs
pydub
networkx
fastapi
uvicorn[standard]
python-multipart
feedgen
apscheduler
pytest
pytest-asyncio
httpx
respx
```

**Acceptance criteria:**
- `from core.models import Paper, QueryParameters, Episode` works with no errors
- `from core.config import CLAUDE_MODEL` raises `ValueError` if env not set
- `pytest tests/unit/test_models.py` passes

**Commit message:** `feat(core): Pydantic v2 models and config loader`

---

## Task 2 — arXiv Client

**Module:** `fetcher`
**Files to create:**
- `core/arxiv_client.py`
- `tests/unit/test_arxiv_client.py`

### `core/arxiv_client.py`
Implement `async def fetch_papers(query: QueryParameters) -> list[Paper]`:

1. Build arXiv search query from `query.topic` + `query.disciplines` (use arXiv category codes where applicable: cs.LG for ML, cs.CL for NLP, q-bio.* for bio, etc.)
2. Set `sort_by=arxiv.SortCriterion.SubmittedDate`, `max_results=query.max_papers`
3. Filter by `query.publication_date_range`
4. If `query.include_preprints=False`, skip papers with no journal_ref
5. Map each `arxiv.Result` to a `Paper` model
6. If `query.study_data_period` is set: call Claude to extract study period from abstract. Prompt:
   ```
   Extract the temporal scope of data used in this research (not when the paper was published).
   Return a JSON object: {"start_year": int|null, "end_year": int|null}
   If no specific data period is mentioned, return nulls.
   Abstract: {abstract}
   ```
   Set `paper.study_period_start` and `paper.study_period_end` from the response. Flag low-confidence cases (both nulls) with a log warning.
7. Respect `ARXIV_RATE_LIMIT_SECONDS` delay between requests
8. Return `list[Paper]`

### `tests/unit/test_arxiv_client.py`
Mock the `arxiv.Client` using `unittest.mock.patch`. Do not make real API calls.

Test cases:
- Basic query returns list of Papers
- Date range filtering works correctly
- `include_preprints=False` filters preprints
- Study period extraction is called when `study_data_period` is set
- Rate limiting delay is applied
- Empty results returns empty list

**Acceptance criteria:** `pytest tests/unit/test_arxiv_client.py -v` passes, 0 API calls made

**Commit message:** `feat(fetcher): arxiv client with date filtering and study period extraction`

---

## Task 3 — Semantic Scholar Client

**Module:** `fetcher`
**Files to create:**
- `core/semantic_scholar_client.py`
- `tests/unit/test_semantic_scholar_client.py`

### `core/semantic_scholar_client.py`
Implement `async def enrich_papers(papers: list[Paper]) -> list[Paper]`:

1. For each paper, search Semantic Scholar by arXiv ID (`arxiv:{arxiv_id}`)
2. Retrieve: `citationCount`, `influentialCitationCount`, `tldr.text`
3. Compute `citation_velocity = citation_count / max(years_since_publication, 1)`
4. Set `paper.citation_count`, `paper.citation_velocity`, `paper.s2_tldr`
5. If S2 can't find a paper (not indexed yet), log a warning and return paper unchanged
6. Use `SEMANTIC_SCHOLAR_API_KEY` if set; otherwise use unauthenticated (lower rate limits)
7. Respect a 1s delay between S2 requests

### `tests/unit/test_semantic_scholar_client.py`
Mock the `semanticscholar` SDK. Test:
- Successful enrichment sets all three fields
- Missing S2 paper returns paper unchanged with a warning
- citation_velocity calculation is correct
- Rate limiting delay is applied

**Acceptance criteria:** `pytest tests/unit/test_semantic_scholar_client.py -v` passes

**Commit message:** `feat(fetcher): semantic scholar enrichment client`

---

## Task 4 — Knowledge Graph

**Module:** `graph`
**Files to create:**
- `core/knowledge_graph.py`
- `tests/unit/test_knowledge_graph.py`

### `core/knowledge_graph.py`
Implement a `KnowledgeGraph` class:

```python
class KnowledgeGraph:
    def __init__(self): ...          # Load from GRAPH_PATH if exists, else create new DiGraph
    def add_paper(self, paper: Paper) -> str: ...  # Returns node_id; sets first_seen_date on creation
    def add_concept(self, name: str, description: str = "") -> str: ...
    def add_method(self, name: str) -> str: ...
    def add_dataset(self, name: str, temporal_scope: Optional[tuple] = None) -> str: ...
    def add_author(self, name: str) -> str: ...
    def add_edge(self, source_id: str, target_id: str, edge_type: str, **attrs) -> None: ...
    def get_node(self, node_id: str) -> dict: ...
    def get_neighbors(self, node_id: str) -> list[dict]: ...
    def search(self, query: str) -> list[dict]: ...  # Substring match on title/name/description
    def update_paper_rating(self, arxiv_id: str, rating: PaperRating) -> None: ...
    def get_delta_papers(self, since: date) -> list[dict]: ...  # Papers with first_seen_date >= since
    def to_d3_json(self) -> dict: ...  # {"nodes": [...], "links": [...]} for D3.js
    def save(self) -> None: ...  # Write to GRAPH_PATH (GraphML) and GRAPH_SNAPSHOT_PATH (JSON)
```

Key rules:
- Deduplication: Papers by `arxiv_id`; Concepts by normalized name (lowercase, spaces→underscores); Authors by exact name
- Every node must have `node_type`, `first_seen_date`, and `label` attributes
- `add_*` methods are idempotent — calling twice with same key updates attrs, doesn't create duplicates
- `save()` is called automatically after every `add_*` and `add_edge` call
- `to_d3_json()` format:
  ```json
  {
    "nodes": [{"id": "...", "label": "...", "node_type": "Paper", "citation_count": 42, ...}],
    "links": [{"source": "...", "target": "...", "edge_type": "CITES"}]
  }
  ```

### `tests/unit/test_knowledge_graph.py`
Use a temp directory (pytest `tmp_path` fixture) for graph file operations.

Test cases:
- `add_paper` creates node with correct attributes
- `add_paper` called twice with same arxiv_id is idempotent (no duplicate)
- `first_seen_date` is set on creation, not overwritten on subsequent calls
- `add_concept` normalizes name to lowercase_with_underscores
- `add_edge` creates edge with edge_type attribute
- `get_delta_papers` returns only papers added since given date
- `update_paper_rating` sets interest_score, depth_score, flagged_for_reading on node
- `to_d3_json` produces valid structure
- `save` and reload preserves all node attributes

**Acceptance criteria:** `pytest tests/unit/test_knowledge_graph.py -v` passes

**Commit message:** `feat(graph): NetworkX knowledge graph with append-only operations`

---

## Task 5 — Audio Processor

**Module:** `voice`
**Files to create:**
- `core/audio_processor.py`
- `tests/unit/test_audio_processor.py`

### `core/audio_processor.py`
Implement:

```python
def stitch_episode(
    segment_paths: list[Path],   # Ordered list of per-turn MP3 files
    output_path: Path,
    silence_between_ms: int = 400
) -> Path:
    """Concatenate segments with silence between each, export as 128kbps MP3."""
    ...

def normalize_audio(audio_segment: AudioSegment, target_dbfs: float = -20.0) -> AudioSegment:
    """Normalize audio level to target dBFS."""
    ...
```

- Use `pydub.AudioSegment` throughout
- Create parent directories if they don't exist
- Return the path to the assembled file

### `tests/unit/test_audio_processor.py`
Generate tiny synthetic audio segments in-memory (no ElevenLabs calls):

Test cases:
- `stitch_episode` with 3 segments produces a file longer than the sum of inputs (due to silence)
- Output file exists at the specified path
- `normalize_audio` adjusts dBFS within tolerance

**Acceptance criteria:** `pytest tests/unit/test_audio_processor.py -v` passes (requires `ffmpeg` installed)

**Commit message:** `feat(voice): pydub audio stitching and normalization`

---

## Task 6 — Fetcher Agent

**Module:** `fetcher`
**Files to create:**
- `agents/fetcher_agent.py`

### `agents/fetcher_agent.py`
Implement `async def run(query: QueryParameters) -> list[Paper]`:

1. Call `arxiv_client.fetch_papers(query)` → raw papers
2. Call `semantic_scholar_client.enrich_papers(papers)` → enriched papers
3. Apply expertise-level filtering:
   - `novice`: sort by `citation_count DESC` (foundational/influential papers first), bias toward survey papers (title contains "survey", "review", "introduction", "overview")
   - `intermediate`: sort by citation_velocity DESC (active, debated work)
   - `expert`: sort by `published_date DESC` (most recent frontier work); deprioritize survey papers
   - If `user_profile` is set, apply the relevant discipline's expertise level; fall back to `default_level`
4. Save papers to `data/papers/{episode_id}.json`
5. Return filtered, sorted `list[Paper]`

Note: `episode_id` is passed in from the orchestrator. Generate it in the orchestrator as: `{date}_{slugified_topic}_{uuid4()[:4]}`

**No unit test for this file** — the underlying clients are already tested. Integration test covers this.

**Commit message:** `feat(fetcher): fetcher agent with expertise-level paper selection`

---

## Task 7 — Bibliography Agent

**Module:** `bibliography`
**Files to create:**
- `agents/bibliography_agent.py`
- `tests/unit/test_bibliography_agent.py`

### `agents/bibliography_agent.py`
Implement `async def run(papers: list[Paper], query: QueryParameters) -> Path`:

For each paper, call Claude to generate an annotated bibliography entry. Prompt:

```
You are generating an annotated bibliography entry for a research podcast.

Paper: {title}
Authors: {authors}
Published: {published_date}
Abstract: {abstract}
Citation count: {citation_count}
TLDR: {s2_tldr}

User expertise level for {discipline}: {expertise_level}

Write an annotated bibliography entry with:
1. Full citation (APA format)
2. 2–3 sentence annotation adapted to the user's expertise level:
   - novice: explain what the paper does in plain language, why it matters, define key terms
   - intermediate: focus on methodology and key findings, note debates it engages with
   - expert: focus on novel contributions, limitations, open questions, and how it contradicts or extends prior work

Return only the formatted annotation text, no extra commentary.
```

After all papers are processed:
- Assemble into a single Markdown file with an intro paragraph synthesizing the episode's theme
- Save to `data/bibliographies/{episode_id}.md`
- Return the file path

### `tests/unit/test_bibliography_agent.py`
Mock the `anthropic.Anthropic` client. Test:
- Returns a Path object
- Output file exists with content
- Expertise level is passed in the prompt
- All papers are included in output

**Commit message:** `feat(bibliography): annotated bibliography agent with expertise-level adaptation`

---

## Task 8 — Graph Agent

**Module:** `graph`
**Files to create:**
- `agents/graph_agent.py`

### `agents/graph_agent.py`
Implement `async def run(papers: list[Paper], episode_id: str) -> KnowledgeGraph`:

For each paper:
1. Add paper node via `graph.add_paper(paper)`
2. Add author nodes and `CO_AUTHORED_BY` edges
3. Call Claude to extract entities/relationships from abstract. Prompt:
   ```
   Extract structured knowledge from this research paper abstract.

   Return a JSON object with these fields:
   {
     "concepts": [{"name": str, "description": str}],
     "methods": [{"name": str}],
     "datasets": [{"name": str, "temporal_scope": str|null}],
     "cites": [{"title_fragment": str}],
     "concept_relationships": [{"from": str, "to": str, "relationship": str}]
   }

   Abstract: {abstract}
   Keep names concise (2–5 words). Only extract what is clearly stated.
   ```
4. Add extracted concept, method, and dataset nodes
5. Add `STUDIES_CONCEPT`, `USES_METHOD`, `APPLIED_TO_DATASET` edges from paper to each
6. Add `RELATED_TO` edges between concepts where specified
7. After all papers processed, save graph

Return the updated `KnowledgeGraph` instance.

**No separate unit test** — knowledge_graph.py is already tested. Integration test covers the agent.

**Commit message:** `feat(graph): graph agent with LLM entity/relation extraction`

---

## Task 9 — Script Agent

**Module:** `script`
**Files to create:**
- `agents/script_agent.py`
- `tests/unit/test_script_agent.py`

### `agents/script_agent.py`
Implement `async def run(papers: list[Paper], bibliography_path: Path, graph: KnowledgeGraph, query: QueryParameters) -> PodcastScript`:

Call Claude with the full context to generate a two-host dialogue script. Prompt structure:

```
You are writing a podcast script for PapersPod, a research podcast.

EPISODE TOPIC: {query.topic}
DISCIPLINES: {query.disciplines}
FOCUS MODE: {query.focus_mode}
USER EXPERTISE: {expertise_summary}

PAPERS DISCUSSED:
{papers_summary}  # title, authors, date, TLDR, key concepts from graph

KNOWLEDGE GRAPH CONTEXT:
{graph_context}  # Key concepts, methods, datasets, and relationships from the graph
                  # Include cross-paper relationships: which papers share concepts, which contradict each other

ANNOTATED BIBLIOGRAPHY:
{bibliography_content}

Generate a natural, engaging two-host podcast dialogue.

HOST A (Alex): Expert explainer. Knowledgeable, precise, uses appropriate terminology for the expertise level.
HOST B (Jordan): Curious generalist. Asks clarifying questions, draws out implications, keeps the conversation accessible.

Rules:
- 800–1200 words total (approximately 6–8 minutes of audio)
- Open with a hook that establishes why this topic matters right now
- Cover all {n} papers but weave them into a narrative, not a list
- Include at least one moment of "this paper actually contradicts what {other paper} said"
- Close with what questions remain open
- Adapt depth to expertise level: {expertise_description}
- Format as alternating HOST A / HOST B turns

Return a JSON array of turns:
[{"host": "A", "text": "..."}, {"host": "B", "text": "..."}, ...]
```

Parse response into `PodcastScript` model. Save:
- `data/scripts/{episode_id}.json` — structured turns
- `data/scripts/{episode_id}.md` — human-readable formatted script

### `tests/unit/test_script_agent.py`
Mock the Claude client. Test:
- Returns a `PodcastScript` with at least 4 turns
- Both "A" and "B" hosts appear in turns
- Script is saved to both JSON and MD paths

**Commit message:** `feat(script): two-host dialogue script agent with graph-aware narration`

---

## Task 10 — Voice Agent

**Module:** `voice`
**Files to create:**
- `agents/voice_agent.py`
- `tests/unit/test_voice_agent.py`

### `agents/voice_agent.py`
Implement `async def run(script: PodcastScript) -> Path`:

1. Create segment directory: `data/audio/segments/{episode_id}/`
2. For each `DialogueTurn` in `script.turns`:
   - Select voice: `ELEVENLABS_VOICE_A_ID` for Host A, `ELEVENLABS_VOICE_B_ID` for Host B
   - Call ElevenLabs to generate audio for `turn.text`
   - Save to `data/audio/segments/{episode_id}/{index:03d}_{host}.mp3`
   - Set `turn.audio_segment_path` to the saved path
3. Call `audio_processor.stitch_episode(segment_paths, output_path)` where `output_path = data/audio/{episode_id}.mp3`
4. Return the assembled episode path

Handle ElevenLabs rate limits: if a 429 is returned, wait 5 seconds and retry once.

### `tests/unit/test_voice_agent.py`
Mock the ElevenLabs client. Test:
- All turns generate segment files
- `stitch_episode` is called with correct segment paths in order
- Returns the correct output path
- 429 retry logic is triggered on rate limit

**Commit message:** `feat(voice): ElevenLabs two-voice agent with pydub stitching`

---

## Task 11 — Orchestrator

**Module:** `orchestrator`
**Files to create:**
- `agents/orchestrator.py`

### `agents/orchestrator.py`
Implement the CLI entry point and pipeline coordinator.

```python
# CLI usage:
# python -m agents.orchestrator \
#   --topic "attention mechanisms" \
#   --disciplines "machine learning" \
#   --focus-mode depth \
#   --publication-start 2022-01-01 \
#   --publication-end 2026-01-01 \
#   --max-papers 3 \
#   --expertise-level expert

# Optional:
#   --cross-disciplinary
#   --include-preprints
#   --study-data-start 2020-01-01
#   --study-data-end 2024-12-31
```

Pipeline sequence:
```
1. Parse CLI args → QueryParameters
2. Generate episode_id
3. Load KnowledgeGraph (creates new if first run)
4. fetcher_agent.run(query) → papers
5. bibliography_agent.run(papers, query) → bibliography_path
6. graph_agent.run(papers, episode_id) → updated graph
7. script_agent.run(papers, bibliography_path, graph, query) → script
8. voice_agent.run(script) → audio_path
9. Build Episode model, save to data/papers/{episode_id}_episode.json
10. Print summary: episode_id, papers count, audio_path, graph stats
```

Log each step at INFO level with timing. If any step fails, log at ERROR and exit with code 1.

**No unit test** — covered by integration test.

**Commit message:** `feat(orchestrator): CLI pipeline coordinator`

---

## Task 12 — Integration Test + Final Validation

**Module:** `orchestrator`
**Files to create:**
- `tests/integration/test_pipeline.py`
- `tests/fixtures/sample_papers.json`

### `tests/fixtures/sample_papers.json`
Create 3 realistic mock paper objects (hardcoded JSON) to use in tests instead of real API calls.

### `tests/integration/test_pipeline.py`
Integration test that mocks all external API calls but runs the full pipeline logic:

1. Mock `arxiv.Client.results()` to return fixture papers
2. Mock Semantic Scholar API to return enriched data
3. Mock Anthropic API to return plausible but short responses
4. Mock ElevenLabs API to return tiny valid MP3 bytes
5. Run full pipeline via `agents/orchestrator` logic (not CLI, call functions directly)
6. Assert:
   - `data/audio/{episode_id}.mp3` exists
   - `data/graphs/graph.graphml` exists and has >= 3 nodes
   - `data/bibliographies/{episode_id}.md` exists and has content
   - `data/scripts/{episode_id}.json` has turns with both "A" and "B" hosts
   - Episode JSON file is saved correctly

**Acceptance criteria:** `pytest tests/integration/test_pipeline.py -v` passes with all mocks

**Commit message:** `test(integration): full pipeline integration test with mocked APIs`

---

## Phase 1 Complete

After Task 12, verify the Phase 1 definition of done in `CLAUDE.md`:
- [ ] `pytest tests/unit/` — all pass
- [ ] `pytest tests/integration/` — all pass
- [ ] Manual run with real API keys produces an MP3
- [ ] All 12 tasks committed to local git

**Final commit message:** `chore: Phase 1 CLI pipeline complete`
