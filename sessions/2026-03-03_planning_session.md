# Session Log — 2026-03-03: Planning & Scaffold

**Session type:** RePPIT Planning + Project Setup
**Status at end of session:** Phase 1 task file complete, repo initialized, ready for autonomous agent execution

---

## What Was Accomplished

### RePPIT Steps Completed
- **Research:** Domain landscape survey (arXiv API, knowledge graph options, TTS providers, competitive tools)
- **Propose:** Orthogonal paths identified and evaluated for all major decisions
- **Plan:** Full plan document written to `PapersPod_Plan.md`
- **Implement / Test:** Not started — Phase 1 agent session is next

### Files Created This Session
| File | Purpose |
|---|---|
| `PapersPod_Plan.md` | Full RePPIT plan with architecture, data models, phases, testing strategy |
| `CLAUDE.md` | Agent project bible — read by every spawned sub-agent automatically |
| `tasks/phase1.md` | 12 granular, numbered, executable tasks for Phase 1 CLI pipeline |
| `.env.example` | API key template |
| `.gitignore` | Excludes `.env`, `data/audio/`, `logs/`, Python artifacts |
| `sessions/` | This directory — tracked human-readable build session logs |

### Architecture Decisions Locked

| Decision | Choice |
|---|---|
| Knowledge graph | NetworkX (MVP) → Neo4j migration path at ~10K nodes |
| AI orchestration | Claude Agent SDK, module-per-agent dev model |
| TTS | ElevenLabs, two voices (Host A + Host B) |
| Podcast format | Two-host dialogue (not single narrator) |
| Audio processing | `pydub` + `ffmpeg` for per-turn stitching |
| Secondary data source | arXiv + Semantic Scholar (citation counts, velocity, TLDR) |
| Web framework | FastAPI |
| Graph visualizer | D3.js force-directed in web player |
| Delivery phases | CLI (Phase 1) → Web player (Phase 2) → Scheduling (Phase 3) → RSS (Phase 4) |
| Dev agent model | Module-per-agent, each owns specific files with guardrails |
| Git | Local only (Phase 1); push to GitHub later |

### Key Product Features Decided

**Human-in-the-loop query parameters:**
- `topic` — primary search query
- `disciplines` — list, supports cross-disciplinary
- `focus_mode` — depth (methodological) vs. breadth (landscape)
- `publication_date_range` — when papers were published
- `study_data_period` — when the *data referenced* in papers is from (non-standard, key differentiator)
- `max_papers`, `include_preprints`
- `user_profile` — per-discipline expertise levels

**Expertise levels (novice / intermediate / expert):**
- Affects paper selection (foundational vs. frontier)
- Affects bibliography tone (analogies vs. technical depth)
- Affects script generation (explanation style, assumed vocabulary)
- Applied per-discipline for cross-disciplinary episodes

**Paper rating + reading queue (post-episode):**
- Users rate each paper: interest_score (1–5), depth_score (1–5), flag_for_reading
- Ratings stored as node attributes in knowledge graph
- High-rated papers weighted in future episode selection
- Flagged papers seed future episode queries automatically

**Knowledge graph:**
- Append-only (never delete nodes/edges)
- Node types: Paper, Concept, Method, Dataset, Author, Institution
- Edge types: CITES, USES_METHOD, STUDIES_CONCEPT, APPLIED_TO_DATASET, CO_AUTHORED_BY, AFFILIATED_WITH, RELATED_TO
- Temporal indexing: published_date, study_period_start/end, first_seen_date (for delta episodes)
- D3.js force-directed visualizer in web player
- Node size proportional to citation count / interest score

### Competitive Landscape Summary
- **No existing tool** combines: arxiv-native auto-ingestion + multi-paper narrative audio + knowledge graph + RSS
- **Google NotebookLM** is closest competitor: good podcast audio, but manual upload only, no graph, no expertise tuning, no RSS, no mobile
- **ResearchRabbit** has the best citation graph but zero audio
- **Podcastfy** (open source) handles paper→audio but no discovery, no graph, single narrator
- **Key unoccupied niche confirmed:** PapersPod bridges all four pillars that no existing tool combines

---

## Dev Agent Module Ownership (Reference)

| Agent | Owns | Guardrails |
|---|---|---|
| `orchestrator` | `agents/orchestrator.py`, `core/models.py`, `core/config.py` | Coordinates only |
| `fetcher` | `agents/fetcher_agent.py`, `core/arxiv_client.py`, `core/semantic_scholar_client.py`, tests | arXiv + S2 APIs only |
| `bibliography` | `agents/bibliography_agent.py`, tests | Reads papers, writes bibliographies |
| `graph` | `agents/graph_agent.py`, `core/knowledge_graph.py`, tests | Reads papers + bibs, writes graphs |
| `script` | `agents/script_agent.py`, tests | Reads graph + bibs, writes scripts |
| `voice` | `agents/voice_agent.py`, `core/audio_processor.py`, tests | Reads scripts, calls ElevenLabs, writes audio |
| `web` | `web/`, integration tests | Read-only on data/ |

---

## Phase 1 Definition of Done

- [ ] `pytest tests/unit/` — 0 failures
- [ ] `pytest tests/integration/` — 0 failures
- [ ] Manual run with real API keys produces an MP3
- [ ] `data/graphs/graph.graphml` has ≥ 5 nodes
- [ ] All 12 tasks committed to local git

---

## Next Session: Phase 1 Implementation

**To start:** Launch an orchestrator agent session pointing at `tasks/phase1.md`. The agent will read `CLAUDE.md` automatically and work through tasks 1–12 in order.

**Before starting, you need to:**
1. Copy `.env.example` → `.env`
2. Fill in `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_A_ID`, `ELEVENLABS_VOICE_B_ID`
3. Install `ffmpeg`: `brew install ffmpeg`
4. Create virtual environment: `python -m venv .venv && source .venv/bin/activate`
5. Install deps: `pip install -r requirements.txt` (once `requirements.txt` is generated in Task 1)

**Suggested agent launch prompt:**
> Read CLAUDE.md and tasks/phase1.md fully. Execute tasks 1–12 in order. After each task, run the relevant unit tests and commit. Do not proceed to the next task until current tests pass. Report progress after each task completes.

---

## Open Questions for Future Sessions
- Mobile app: native (Swift/Kotlin) vs. React Native vs. PWA?
- Authentication: when to add it (Phase 2 or later)?
- Community/social layer: share curated episode collections with collaborators?
- Post-episode Q&A: user asks follow-up question, gets spoken AI answer?
- Neo4j migration trigger: auto-detect at 10K nodes, or manual?
