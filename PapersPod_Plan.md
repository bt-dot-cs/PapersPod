# PapersPod — RePPIT Plan
**Date:** 2026-03-03
**Framework:** RePPIT (Research → Propose → Plan → Implement → Test)

---

## 1. Research

### What PapersPod Is
An automated research-to-podcast pipeline that:
1. Queries arXiv for research papers using rich user-defined parameters
2. Generates annotated bibliography drafts via Claude
3. Builds and expands a persistent knowledge graph from extracted concepts
4. Generates a podcast script from the graph + bibliography
5. Converts the script to audio via ElevenLabs
6. Serves everything through a FastAPI web app with a D3.js knowledge graph visualizer and podcast player

### External APIs & SDKs
| Service | Usage | Notes |
|---|---|---|
| `arxiv` Python package | Fetch papers | Official wrapper; replaces raw HTTP + XML parsing |
| Semantic Scholar API | Citation counts, citation velocity, TLDR summaries | `semanticscholar` Python SDK; supplements arXiv metadata |
| Anthropic SDK (Claude) | Bibliography + script generation | claude-sonnet-4-6 for generation, orchestration via Agent SDK |
| ElevenLabs API | Text-to-speech (two voices) | Key required, podcast-quality; one voice per host |
| `pydub` + `ffmpeg` | Audio post-processing | Stitch per-turn audio segments, normalize levels |
| FastAPI | Web player + REST API | Async Python backend |
| D3.js | Knowledge graph visualizer | Force-directed graph in browser |
| NetworkX | Graph data structure | Python-native, serialize to JSON/GraphML |
| `feedgen` | RSS 2.0 podcast feed | Phase 4 distribution |

---

## 2. Propose

### Key Decisions Made
| Decision | Choice | Rationale |
|---|---|---|
| Knowledge graph backend | NetworkX → Neo4j migration path | Zero infra MVP, Neo4j when graph exceeds ~100K nodes |
| AI orchestration | Claude Agent SDK | Sub-agent pattern for both app pipeline and dev workflow |
| TTS provider | ElevenLabs | Best podcast-quality voice output |
| Delivery | Local → Web player → RSS | Progressive enhancement per phase |
| Trigger | Manual now, scheduled later | MVP validates pipeline, scheduling added in Phase 3 |
| Web framework | FastAPI | Async, auto-docs, natural fit with async agents |
| Graph visualizer | D3.js in web player | Force-directed, click-to-expand, alongside podcast player |
| Dev agent model | Module-per-agent | Tight scope, clean audit trail, strong guardrails |
| Podcast format | Two-host dialogue | Host A (expert explainer) + Host B (curious generalist); conversational, not lecture-style |
| Secondary data source | arXiv + Semantic Scholar | Citation counts + velocity + TLDR improves paper selection quality |

---

## 3. Plan

### Human-in-the-Loop Parameters

The user configures each podcast episode with the following parameters:

```python
class ExpertiseLevel(str, Enum):
    novice       = "novice"        # Include foundational papers, define jargon, use analogies
    intermediate = "intermediate"  # Assume core concepts, focus on methodology and debates
    expert       = "expert"        # Skip basics, frontier papers, edge cases, null results

class ExpertiseProfile(BaseModel):
    discipline: str                # e.g., "machine learning"
    level: ExpertiseLevel

class UserProfile(BaseModel):
    expertise: list[ExpertiseProfile]   # Per-discipline expertise levels
    default_level: ExpertiseLevel       # Fallback for unlisted disciplines

class QueryParameters(BaseModel):
    topic: str                                      # Primary search query
    disciplines: list[str]                          # e.g., ["machine learning", "neuroscience"]
    cross_disciplinary: bool                        # Pull from multiple fields
    focus_mode: Literal["depth", "breadth"]         # Methodological vs. landscape sweep
    publication_date_range: tuple[date, date]       # When papers were published
    study_data_period: Optional[tuple[date, date]]  # When referenced data is from
                                                    # (e.g. 2025 paper with 1990s data)
    max_papers: int                                 # Number of papers to retrieve
    include_preprints: bool                         # Allow unreviewed arXiv preprints
    user_profile: Optional[UserProfile]             # Expertise levels by discipline
```

The `study_data_period` parameter is non-standard. It requires extracting the temporal scope of referenced datasets from paper abstracts — this is a key differentiator vs. other tools.

The `user_profile` shapes both paper selection and script generation:
- **novice**: bibliography includes foundational surveys and seminal papers; script uses analogies, defines terms, explains "why this matters"
- **intermediate**: methodology focus, assumes basics, surfaces key debates
- **expert**: frontier papers only, skip foundational context, focus on novel contributions, limitations, open questions, and contradictions with prior work

For cross-disciplinary queries, expertise is applied per-discipline — a user can be an expert in ML but a novice in neuroscience in the same episode.

---

### Paper Rating Model

Post-episode, users rate papers to build a feedback loop into the graph:

```python
class PaperRating(BaseModel):
    paper_id: str                  # arXiv ID
    episode_id: str
    interest_score: int            # 1–5: how interesting was this paper
    depth_score: int               # 1–5: want to go deeper on this paper
    flag_for_reading: bool         # Add to "read more closely" queue
    notes: Optional[str]           # Freeform annotation

class ReadingQueueItem(BaseModel):
    paper_id: str
    added_date: date
    priority: int                  # User-set or derived from depth_score
    status: Literal["queued", "reading", "done"]
```

Ratings are stored as node attributes on `Paper` nodes in the knowledge graph (`paper.interest_score`, `paper.depth_score`). High-rated papers have elevated weight in future episode paper selection and are surfaced more prominently in the D3.js visualizer. "Flag for reading" papers seed future episode queries automatically.

---

### Application Architecture

#### Pipeline (Claude Agent SDK)

```
User Query Parameters
        │
        ▼
┌─────────────────────────────────────────────────────┐
│                  Orchestrator Agent                  │
│              (agents/orchestrator.py)               │
└───────────┬─────────────────────────────────────────┘
            │
            ▼
    ┌──────────────┐
    │ FetcherAgent │
    │ arXiv query  │
    └──────┬───────┘
           │
           ▼
    ┌──────────────────┐
    │ BibliographyAgent│
    │ annotated drafts │
    └──────┬───────────┘
           │
           ▼
    ┌──────────────┐
    │  GraphAgent  │
    │ NetworkX     │
    └──────┬───────┘
           │
           ▼
    ┌─────────────────────────┐
    │       ScriptAgent       │
    │ two-host dialogue script│
    │ (Host A / Host B turns) │
    └──────────┬──────────────┘
               │
               ▼
    ┌─────────────────────────┐
    │       VoiceAgent        │
    │ ElevenLabs × 2 voices   │
    │ pydub segment stitching │
    └──────────┬──────────────┘
               │
               ▼
        data/audio/*.mp3
```

#### Web Application (FastAPI + D3.js)

```
FastAPI App (web/app.py)
├── POST /pipeline/run               → Trigger pipeline with QueryParameters
├── GET  /episodes                   → List all generated episodes
├── GET  /episodes/{id}/stream       → Stream MP3
├── GET  /episodes/{id}/download     → Download MP3
├── GET  /episodes/{id}/script       → Return podcast script text
├── POST /episodes/{id}/ratings      → Submit paper ratings for an episode
├── GET  /reading-queue              → Get flagged-for-reading papers
├── PATCH /reading-queue/{paper_id}  → Update reading status
├── GET  /profile                    → Get user expertise profile
├── PUT  /profile                    → Update expertise levels per discipline
├── GET  /graph                      → Return full knowledge graph (JSON for D3)
├── GET  /graph/node/{id}            → Node detail + neighbors
└── GET  /graph/search               → Search graph by concept/paper/author

Note: Mobile app (future) consumes the same API — design endpoints with mobile client in mind
from Phase 2 onward (pagination, lightweight payloads, auth-ready but auth not required for MVP).
```

---

### Knowledge Graph Data Model

**Node types:**
- `Paper` — arXiv ID, title, authors, published_date, study_period, abstract
- `Concept` — extracted topic/theme, description
- `Method` — research method/technique
- `Dataset` — named dataset, temporal scope
- `Author` — researcher
- `Institution` — affiliated org

**Edge types:**
- `CITES` — Paper → Paper
- `USES_METHOD` — Paper → Method
- `STUDIES_CONCEPT` — Paper → Concept
- `APPLIED_TO_DATASET` — Paper → Dataset
- `CO_AUTHORED_BY` — Paper → Author
- `AFFILIATED_WITH` — Author → Institution
- `RELATED_TO` — Concept → Concept (cross-disciplinary links)

**Temporal indexing:**
- `paper.published_date` — when the paper was published
- `paper.study_period_start / study_period_end` — temporal scope of referenced data (extracted from abstract via Claude)
- `paper.first_seen_date` — when the paper was first added to the graph (enables delta/incremental episodes: "new since last run")

**Rating attributes (stored on Paper nodes):**
- `paper.interest_score` — user rating, 1–5
- `paper.depth_score` — user's desired depth, 1–5
- `paper.flagged_for_reading` — bool

**Semantic Scholar enrichment (stored on Paper nodes):**
- `paper.citation_count` — total citations (proxy for influence)
- `paper.citation_velocity` — citations per year (proxy for recency of impact)
- `paper.s2_tldr` — one-sentence AI summary from Semantic Scholar

The graph is append-only — each pipeline run adds new nodes and edges without removing existing ones. Deduplication by arXiv ID and concept normalized string.

---

### Project File Structure

```
PapersPod/
├── agents/                         # Application pipeline (Claude Agent SDK)
│   ├── orchestrator.py             # Parent agent, coordinates pipeline
│   ├── fetcher_agent.py            # arXiv queries + paper retrieval
│   ├── bibliography_agent.py       # Annotated bibliography via Claude
│   ├── graph_agent.py              # NetworkX graph build/expand
│   ├── script_agent.py             # Podcast script generation
│   └── voice_agent.py              # ElevenLabs TTS
│
├── core/
│   ├── arxiv_client.py             # arXiv queries via `arxiv` Python package
│   ├── semantic_scholar_client.py  # Semantic Scholar SDK wrapper (citation counts, TLDR)
│   ├── knowledge_graph.py          # NetworkX operations (add, query, serialize)
│   ├── audio_processor.py          # pydub: stitch per-turn MP3 segments, normalize levels
│   ├── models.py                   # Pydantic models: Paper, Node, Edge, Episode, QueryParameters,
│   │                               #   ExpertiseProfile, UserProfile, PaperRating, ReadingQueueItem
│   └── config.py                   # API keys (from env), defaults, voice IDs
│
├── web/
│   ├── app.py                      # FastAPI application
│   ├── routers/
│   │   ├── episodes.py             # Episode list, stream, download, ratings
│   │   ├── graph.py                # Graph query endpoints
│   │   ├── pipeline.py             # Pipeline trigger endpoint
│   │   ├── profile.py              # User expertise profile CRUD
│   │   └── reading_queue.py        # Reading queue management
│   ├── static/
│   │   ├── player.js               # Podcast audio player
│   │   └── graph_viz.js            # D3.js force-directed knowledge graph
│   └── templates/
│       └── index.html              # Single-page app shell
│
├── data/                           # Persistent output (gitignore audio, keep metadata)
│   ├── papers/                     # Raw paper JSON per episode
│   ├── graphs/                     # NetworkX GraphML + JSON snapshots
│   ├── bibliographies/             # Annotated bibliography Markdown
│   ├── scripts/                    # Podcast scripts Markdown
│   └── audio/                      # Generated MP3s (gitignored)
│
├── tests/
│   ├── unit/
│   │   ├── test_arxiv_client.py
│   │   ├── test_semantic_scholar_client.py
│   │   ├── test_knowledge_graph.py
│   │   ├── test_audio_processor.py
│   │   └── test_models.py
│   ├── integration/
│   │   ├── test_pipeline.py        # End-to-end with real API calls (small paper set)
│   │   └── test_api.py             # FastAPI endpoints
│   └── fixtures/
│       └── sample_papers.json      # Mocked arXiv responses
│
├── .env.example
├── requirements.txt
├── Framework_RePPIT.md
└── PapersPod_Plan.md               # This document
```

---

### Dev Agent Architecture (Module-per-Agent)

Each module in the codebase has a dedicated Claude sub-agent that **owns** that module. A thin orchestrator coordinates.

| Agent | Owns | Guardrails |
|---|---|---|
| `orchestrator` | `agents/orchestrator.py`, `core/models.py`, `core/config.py` | Coordinates only, no direct data writes |
| `fetcher` | `agents/fetcher_agent.py`, `core/arxiv_client.py`, `core/semantic_scholar_client.py`, `tests/unit/test_arxiv_client.py`, `tests/unit/test_semantic_scholar_client.py` | Can only call arXiv + Semantic Scholar APIs |
| `bibliography` | `agents/bibliography_agent.py`, `tests/unit/test_bibliography.py` | Reads `data/papers/`, writes `data/bibliographies/` |
| `graph` | `agents/graph_agent.py`, `core/knowledge_graph.py`, `tests/unit/test_knowledge_graph.py` | Reads papers + bibliographies, writes `data/graphs/` |
| `script` | `agents/script_agent.py`, `tests/unit/test_script.py` | Reads graph + bibliography, writes `data/scripts/` |
| `voice` | `agents/voice_agent.py`, `core/audio_processor.py`, `tests/unit/test_voice.py`, `tests/unit/test_audio_processor.py` | Reads scripts, calls ElevenLabs (2 voices), stitches with pydub, writes `data/audio/` |
| `web` | `web/`, `tests/integration/test_api.py` | Read-only on `data/`, writes web static files |

**Audit trail:** Every agent logs to `logs/{module}/YYYY-MM-DD.log` with operation, input hash, output path, and token usage.

---

### Implementation Phases

#### Phase 1 — CLI Pipeline (MVP)
Goal: End-to-end run from query parameters to MP3, no web UI.

Tasks:
- [ ] Project scaffold: directories, `requirements.txt`, `.env.example`, Pydantic models (including ExpertiseProfile, UserProfile, PaperRating)
- [ ] `core/arxiv_client.py` — query arXiv via `arxiv` Python package, return `list[Paper]`
- [ ] `core/semantic_scholar_client.py` — enrich papers with citation counts, velocity, TLDR
- [ ] `core/knowledge_graph.py` — init graph, add nodes/edges, track `first_seen_date`, serialize to JSON/GraphML
- [ ] `core/audio_processor.py` — pydub: stitch Host A/Host B audio segments per turn, normalize, export MP3
- [ ] `agents/fetcher_agent.py` — wraps arxiv_client + semantic_scholar_client, handles QueryParameters, applies expertise-level paper selection (novice → foundational; expert → frontier)
- [ ] `agents/bibliography_agent.py` — sends papers to Claude, adapts output to user expertise level
- [ ] `agents/graph_agent.py` — extracts entities/relations via Claude (GraphRAG-style), updates graph, flags delta papers (new since last run)
- [ ] `agents/script_agent.py` — generates two-host dialogue script (Host A: expert; Host B: curious generalist); includes relationship-aware narration ("this contradicts Smith et al. 2021")
- [ ] `agents/voice_agent.py` — sends each turn to ElevenLabs (voice_a / voice_b), assembles via audio_processor
- [ ] `agents/orchestrator.py` — chains agents, CLI entry point with all QueryParameters flags
- [ ] Unit tests for `arxiv_client`, `semantic_scholar_client`, `knowledge_graph`, `audio_processor`
- [ ] Integration test: 3-paper end-to-end run, assert MP3 exists + graph has nodes + delta tracking works

#### Phase 2 — Web Player
Goal: FastAPI app with D3.js graph visualizer and podcast player.

Tasks:
- [ ] FastAPI app structure + routers
- [ ] Pipeline trigger endpoint (POST /pipeline/run)
- [ ] Episode list + streaming + download endpoints
- [ ] D3.js force-directed knowledge graph (`graph_viz.js`)
  - Nodes colored by type (Paper, Concept, Method, Dataset)
  - Node size proportional to citation count / interest score
  - Click node → expand neighbors, show paper metadata panel
  - Filter by publication date slider
  - Filter by study data period slider
  - Highlight delta papers (added in current session) vs. historical
- [ ] Podcast player UI with transcript panel
  - Transcript synced to audio playback
  - Paper list sidebar with rating widget (1–5 stars, "flag for reading" button)
  - Post-episode rating prompts for each paper discussed
- [ ] User profile page: set expertise level per discipline
- [ ] Reading queue UI: prioritized list of flagged papers
- [ ] Integration tests for API endpoints (including ratings + profile endpoints)
- [ ] Note: all endpoints designed mobile-API-compatible (pagination, lightweight payloads)

#### Phase 3 — Scheduling
Goal: Automated episode generation without manual trigger.

Tasks:
- [ ] APScheduler integration in FastAPI app
- [ ] Topic watchlist config (YAML or JSON)
- [ ] Deduplication: skip papers already in graph
- [ ] Episode history UI

#### Phase 4 — RSS / Distribution
Goal: Subscribable podcast feed.

Tasks:
- [ ] RSS 2.0 feed generation (with podcast namespace)
- [ ] S3 upload for audio files
- [ ] Podcast artwork + episode metadata
- [ ] Submit to Apple Podcasts / Spotify (manual step)

---

### Testing Strategy

#### Unit Tests
- `test_arxiv_client.py` — mock `arxiv` package responses, date filtering, study period extraction
- `test_semantic_scholar_client.py` — mock API responses, citation enrichment, TLDR retrieval
- `test_knowledge_graph.py` — add nodes, add edges, deduplication, `first_seen_date` tracking, rating attribute updates, serialize/deserialize
- `test_audio_processor.py` — segment stitching, silence padding between turns, output format validation
- `test_models.py` — Pydantic model validation, ExpertiseProfile, PaperRating, QueryParameters edge cases

#### Integration Tests
- `test_pipeline.py` — real arXiv API call, 3 papers, full pipeline run, assert MP3 exists + graph has nodes
- `test_api.py` — FastAPI TestClient, all endpoints, including graph JSON structure for D3

#### Metrics & Observability
| Metric | How measured |
|---|---|
| Paper relevance | Embedding cosine similarity vs. query topic |
| Bibliography quality | Claude self-eval (LLM-as-judge, 1-5 score) |
| Graph growth | Node count + edge count per run |
| Audio generation | Success rate, duration vs. script word count |
| API latency | FastAPI middleware timing per endpoint |
| Token usage | Logged per agent per run, summed per episode |

---

### Known Limitations & Risks

| Risk | Mitigation |
|---|---|
| arXiv rate limits | Respect 3s delay between requests, cache paper metadata locally |
| Study period extraction accuracy | Claude may misread ambiguous abstract language — flag low-confidence extractions for human review |
| ElevenLabs cost at scale | Token budget per episode; degrade gracefully to OpenAI TTS if quota exceeded |
| NetworkX memory at scale | Export graph to GraphML after each run; lazy-load on query; plan Neo4j migration at ~10K nodes |
| Two-host audio latency | Each dialogue turn is a separate ElevenLabs call; generate Host A/B turns in parallel where consecutive turns don't depend on each other; stitch with pydub |
| D3.js graph performance | Limit rendered nodes to top-N by centrality; paginate/virtualize on click |

---

### Python Dependencies (requirements.txt)

```
# Core pipeline
arxiv                    # arXiv API client
semanticscholar          # Semantic Scholar API SDK
anthropic                # Claude SDK (Agent SDK)
pydantic>=2.0            # Data models

# Audio
elevenlabs               # TTS API
pydub                    # Audio stitching and processing
# ffmpeg must be installed system-level (brew install ffmpeg)

# Graph
networkx                 # Knowledge graph (in-memory)

# Web
fastapi
uvicorn[standard]
python-multipart         # File uploads

# Distribution
feedgen                  # RSS 2.0 podcast feed (Phase 4)

# Scheduling
apscheduler              # Cron-style episode scheduling (Phase 3)

# Testing
pytest
pytest-asyncio
httpx                    # FastAPI async test client
respx                    # HTTP mock for arxiv/S2 calls
```

---

## 4. Implement

Start with Phase 1 (CLI Pipeline). Each module developed by its dedicated sub-agent, unit-tested before integration.

**Entry point for Phase 1:**
```bash
python -m agents.orchestrator \
  --topic "transformer architectures" \
  --disciplines "machine learning" \
  --focus-mode depth \
  --publication-start 2022-01-01 \
  --publication-end 2026-01-01 \
  --max-papers 5
```

---

## 5. Test

After each phase:
1. Run unit tests for all touched modules
2. Run integration test (real API calls, small paper set)
3. Manual user test: listen to generated episode, read bibliography, interact with graph visualizer
4. Review metrics log: token usage, audio duration, graph growth
5. Document issues as new tasks before next phase begins
