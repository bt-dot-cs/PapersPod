# Session Log — 2026-03-04 Phase 2: OpenAlex + TTS Providers

## Summary

Resumed from phase 1 e2e run. Committed leftover e2e fixes, then built two Phase 2 features: OpenAlex as a second paper source, and pluggable TTS voice providers (OpenAlex, Google Cloud, OpenAI alternatives to ElevenLabs).

---

## Commits This Session

- `65c0ef9` — fix(fetcher,script): arXiv relevance sort + host alias normalization *(leftover from phase 1 e2e run)*
- `0f183a6` — feat(fetcher): OpenAlex integration with auto source routing
- `8fb94bb` — feat(voice): pluggable TTS provider (ElevenLabs, OpenAI, Google)

---

## Feature 1: OpenAlex Integration

### What was built

| File | Change |
|---|---|
| `core/openalex_client.py` | NEW — async `fetch_papers()` via OpenAlex REST API |
| `core/models.py` | `QueryParameters.source` field; `Paper.openalex_id` field |
| `core/config.py` | `OPENALEX_EMAIL`, `OPENALEX_RATE_LIMIT_SECONDS` |
| `agents/fetcher_agent.py` | `_select_source()` routing; imports `openalex_client` |
| `agents/orchestrator.py` | `--source auto\|arxiv\|openalex` CLI flag |
| `tests/unit/test_openalex_client.py` | 14 new tests |

### Key implementation details

- **No API key required** — email in User-Agent for polite pool (not needed for personal use)
- Abstract reconstruction: OpenAlex returns `abstract_inverted_index` (word→position dict); reconstructed to plain text
- Paper ID: arXiv ID used when available (`ids.arxiv`); falls back to OpenAlex work ID (e.g., `W2746350549`)
- Date filter: year range sent to API; Python-side filter on exact dates
- **Discipline → source routing** (`_select_source()`):
  - STEM disciplines → arXiv (default)
  - `economics`, `history`, `sociology`, `political science`, `law`, `anthropology`, `philosophy`, `education`, `psychology`, `communications`, `labor studies`, `science and technology studies`, `sts`, `cultural studies`, `geography`, `history of technology` → OpenAlex
  - `--source auto|arxiv|openalex` overrides the heuristic

### Second pipeline run (partial)

**Topic**: deskilling artisan labor technological displacement
**Parameters**:
```bash
python -m agents.orchestrator \
  --topic "deskilling artisan labor technological displacement" \
  --disciplines "economics" \
  --focus-mode depth \
  --publication-start 2015-01-01 \
  --publication-end 2026-01-01 \
  --max-papers 3 \
  --expertise-level intermediate
```

**Episode ID**: `2026-03-04_deskilling-artisan-labor-technological-d_e16b`

**Papers fetched (OpenAlex)**:
- `W2746350549` — Skilling and deskilling: technological change in classical economics
- `W3106095282` — Understanding the Success of the Know-Nothing Party
- `W4200525695` — Technology, Vintage-Specific Human Capital, and Labor Displacement

**Pipeline progress**:
- [1/5] Fetch: ~66s (OpenAlex fast; S2 enrichment 429 retry added ~60s; all 3 not found in S2 since no arXiv IDs)
- [2/5] Bibliography: completed ✓
- [3/5] Graph: completed ✓
- [4/5] Script: completed ✓ (23 turns)
- [5/5] Audio: **FAILED at turn 8/23** — ElevenLabs free quota exhausted (0 credits remaining)

**Outputs saved** (no audio):
- `data/bibliographies/2026-03-04_deskilling-artisan-labor-technological-d_e16b.md`
- `data/scripts/2026-03-04_deskilling-artisan-labor-technological-d_e16b.json` + `.md`
- `data/graphs/graph.graphml` (updated)

---

## Feature 2: Pluggable TTS Providers

### What was built

| File | Change |
|---|---|
| `core/tts_elevenlabs.py` | NEW — ElevenLabs synthesize extracted from voice_agent, with 429 retry |
| `core/tts_openai.py` | NEW — OpenAI tts-1 synthesize |
| `core/tts_google.py` | NEW — Google Cloud Neural2 synthesize (sync wrapped for async) |
| `core/config.py` | `VOICE_PROVIDER`; ElevenLabs keys → optional; OpenAI/Google keys added |
| `agents/voice_agent.py` | `_voice_id()` + `_synthesize()` routing; simplified run() |
| `requirements.txt` | Added `openai`; `google-cloud-texttospeech` commented out |
| `tests/unit/test_tts_providers.py` | NEW — 7 tests for all three providers |
| `tests/unit/test_voice_agent.py` | Updated to patch `_synthesize`; added routing tests |

**110 unit tests passing.**

### Provider comparison

| Provider | Free tier | Paid | Voice quality |
|---|---|---|---|
| ElevenLabs (default) | 10K chars/mo | $5/mo → 30K | Best |
| OpenAI | $5 credit | $15–30/1M chars | Good |
| Google Cloud | 1M chars/mo | $4–16/1M chars | Good (Neural2) |

### Configuration

Add to `.env`:
```
# To switch providers:
VOICE_PROVIDER=openai          # or: elevenlabs (default), google

# OpenAI TTS
OPENAI_API_KEY=sk-...
OPENAI_TTS_VOICE_A=nova        # optional, default: nova (female)
OPENAI_TTS_VOICE_B=onyx        # optional, default: onyx (male)

# Google Cloud TTS (also requires GOOGLE_APPLICATION_CREDENTIALS)
# GOOGLE_TTS_VOICE_A=en-US-Neural2-F
# GOOGLE_TTS_VOICE_B=en-US-Neural2-D
```

---

## Pending: Complete Deskilling Episode

The `e16b` episode has script + bibliography but no audio. To complete it, add `OPENAI_API_KEY` to `.env`, set `VOICE_PROVIDER=openai`, and re-run. The episode will get a new ID (a fresh run), not resume the partial one.

A `--skip-to-audio <episode_id>` flag was discussed but not yet built — would allow re-running only step 5 with an existing script.

---

## Current .env State

```
ANTHROPIC_API_KEY=set
ELEVENLABS_API_KEY=set (quota exhausted for this month)
ELEVENLABS_VOICE_A_ID=XrExE9yKIg1WjnnlVkGX  (Matilda, free)
ELEVENLABS_VOICE_B_ID=SAz9YHcvj6GT2YYXdXww  (River, free)
VOICE_PROVIDER=elevenlabs  (default — change to openai once key added)
OPENAI_API_KEY=  (not yet set)
SEMANTIC_SCHOLAR_API_KEY=  (waiting on approval)
```

---

## Next Steps

Resume prompt after compact:

> Read CLAUDE.md and sessions/2026-03-04_phase2_openalex_tts_providers.md. OpenAlex integration and TTS provider abstraction are complete. The deskilling episode stalled at audio because ElevenLabs quota was exhausted. To complete it: add OPENAI_API_KEY to .env and set VOICE_PROVIDER=openai, then re-run the deskilling pipeline. Or build --skip-to-audio first to avoid re-spending on steps 1-4.
