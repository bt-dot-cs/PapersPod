"""
PapersPod CLI entry point.

Usage:
    python -m agents.orchestrator \
        --topic "attention mechanisms" \
        --disciplines "machine learning" \
        --focus-mode depth \
        --publication-start 2022-01-01 \
        --publication-end 2026-01-01 \
        --max-papers 3 \
        --expertise-level expert
"""

import argparse
import asyncio
import json
import logging
import time
import uuid
from datetime import date, datetime
from pathlib import Path

from core.config import (
    CLAUDE_INPUT_COST_PER_M_TOKENS,
    CLAUDE_MODEL,
    CLAUDE_OUTPUT_COST_PER_M_TOKENS,
    DATA_DIR,
    TTS_COST_PER_M_CHARS,
    VOICE_PROVIDER,
)
from core.knowledge_graph import KnowledgeGraph
from core.models import (
    Episode,
    ExpertiseLevel,
    ExpertiseProfile,
    QueryParameters,
    TokenUsage,
    UserProfile,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class _WarningCapture(logging.Handler):
    """Collects WARNING and ERROR log records during a pipeline run."""

    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.records: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(f"[{record.levelname}] {record.name}: {record.getMessage()}")


def _generate_episode_id(topic: str) -> str:
    """Format: {YYYY-MM-DD}_{slugified-topic}_{4-char-hex}"""
    today = date.today().isoformat()
    slug = topic.lower().strip().replace(" ", "-")[:40]
    suffix = uuid.uuid4().hex[:4]
    return f"{today}_{slug}_{suffix}"


def _save_partial_manifest(
    episode_id: str,
    query: "QueryParameters",
    usage: "TokenUsage",
    stage_times: dict[str, float],
    voice_provider: str | None,
    bibliography_path: "Path | None",
    warning_capture: "_WarningCapture | None",
) -> None:
    """Write a partial manifest after TTS failure. TTS fields are null; Claude costs are captured."""
    claude_input_cost  = usage.input_tokens  / 1_000_000 * CLAUDE_INPUT_COST_PER_M_TOKENS
    claude_output_cost = usage.output_tokens / 1_000_000 * CLAUDE_OUTPUT_COST_PER_M_TOKENS
    claude_cost = claude_input_cost + claude_output_cost
    tts_provider_requested = voice_provider or VOICE_PROVIDER
    manifest = {
        "episode_id": episode_id,
        "created_at": datetime.now().isoformat(),
        "partial": True,
        "partial_reason": "tts_failure",
        "parameters": {
            "topic": query.topic,
            "disciplines": query.disciplines,
            "source": query.source,
            "max_papers": query.max_papers,
            "expertise_level": query.user_profile.default_level.value,
            "voice_provider_requested": tts_provider_requested,
            "anchor_papers": query.anchor_papers,
            "publication_start": query.publication_date_range[0].isoformat() if query.publication_date_range else None,
            "publication_end": query.publication_date_range[1].isoformat() if query.publication_date_range else None,
        },
        "stage_timings_seconds": {k: round(v, 2) for k, v in stage_times.items()},
        "tokens": {
            "input": usage.input_tokens,
            "output": usage.output_tokens,
        },
        "costs_usd": {
            "claude_input": round(claude_input_cost, 4),
            "claude_output": round(claude_output_cost, 4),
            "claude_total": round(claude_cost, 4),
            "tts": 0.0,
            "total": round(claude_cost, 4),
        },
        "tts": {
            "provider_requested": tts_provider_requested,
            "provider_used": None,
            "fallback_occurred": False,
            "characters": 0,
        },
        "output_files": {
            "audio": None,
            "script": str(DATA_DIR / "scripts" / f"{episode_id}.json"),
            "bibliography": str(bibliography_path) if bibliography_path else None,
            "fetch_trace": str(DATA_DIR / "traces" / f"{episode_id}_fetch.json"),
        },
        "warnings": warning_capture.records if warning_capture else [],
    }
    manifest_path = DATA_DIR / "traces" / f"{episode_id}_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    logger.info("Partial manifest written to %s (Claude costs captured)", manifest_path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PapersPod — research podcast generator")
    parser.add_argument(
        "--skip-to-audio", metavar="EPISODE_ID",
        help="Skip steps 1-4 and generate audio from an existing saved script"
    )
    parser.add_argument("--topic", help="Primary search topic")
    parser.add_argument(
        "--disciplines", nargs="+",
        help="Disciplines to search (e.g. 'machine learning' 'neuroscience')"
    )
    parser.add_argument(
        "--focus-mode", choices=["depth", "breadth"], default="breadth",
        help="depth = methodological focus, breadth = landscape sweep"
    )
    parser.add_argument(
        "--publication-start",
        help="Publication date range start (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--publication-end",
        help="Publication date range end (YYYY-MM-DD)"
    )
    parser.add_argument("--max-papers", type=int, default=5)
    parser.add_argument("--include-preprints", action="store_true", default=True)
    parser.add_argument(
        "--expertise-level", choices=["novice", "intermediate", "expert"],
        default="intermediate"
    )
    parser.add_argument("--cross-disciplinary", action="store_true", default=False)
    parser.add_argument("--study-data-start", help="Study data period start (YYYY-MM-DD)")
    parser.add_argument("--study-data-end", help="Study data period end (YYYY-MM-DD)")
    parser.add_argument(
        "--source", choices=["auto", "arxiv", "openalex", "crossref", "plos", "springer", "ieee", "doaj"], default="auto",
        help="Paper source: auto (default), arxiv, openalex, crossref, plos, springer, ieee, doaj"
    )
    parser.add_argument(
        "--crossref-publisher",
        choices=["sage", "elsevier", "springer", "wiley", "taylor-francis", "oxford", "cambridge", "ieee"],
        default=None,
        help="Publisher for --source crossref (default: sage). e.g. --source crossref --crossref-publisher elsevier"
    )
    parser.add_argument(
        "--voice-provider", choices=["elevenlabs", "elevenlabs_free", "openai", "google"], default=None,
        help="TTS provider override (default: use VOICE_PROVIDER from .env). elevenlabs=premium library voices, elevenlabs_free=premade voices (free-tier accessible)"
    )
    parser.add_argument(
        "--anchor-paper", metavar="ID_OR_TITLE", action="append", dest="anchor_papers",
        help=(
            "Anchor the episode around a specific paper. "
            "Accepts arXiv ID (e.g. 2301.07041), DOI (e.g. 10.1145/...), or a title string. "
            "Related papers are fetched via Semantic Scholar recommendations. "
            "Repeat to provide up to 5 anchor papers: --anchor-paper id1 --anchor-paper id2. "
            "When used, --publication-start and --publication-end are optional (default: last 5 years)."
        )
    )
    parser.add_argument(
        "--enrich", action="store_true", default=False,
        help="Run Semantic Scholar enrichment (citation counts, TLDR) after fetching papers"
    )
    parser.add_argument(
        "--trace-reasoning", action="store_true", default=False,
        help="Write Claude selection reasoning to the fetch trace (~$0.01 extra, ~10s latency)"
    )
    parser.add_argument(
        "--anchor-paper-json", metavar="PATH",
        help=(
            "Path to a JSON file with pre-populated Paper model fields. "
            "Use when the anchor paper is not yet indexed in Semantic Scholar (e.g. recent NeurIPS papers). "
            "Related papers are still fetched via S2 using the anchor title. "
            "When used, --publication-start and --publication-end are optional (default: last 5 years)."
        )
    )
    return parser.parse_args()


async def run_audio_only(episode_id: str, voice_provider: str | None = None) -> tuple[Path, int, str]:
    """Load a saved script and run only the audio generation step."""
    from agents import voice_agent

    if voice_provider:
        voice_agent.VOICE_PROVIDER = voice_provider
        logger.info("Voice provider overridden to: %s", voice_provider)

    script_path = DATA_DIR / "scripts" / f"{episode_id}.json"
    if not script_path.exists():
        raise FileNotFoundError(f"No saved script found at {script_path}")

    from core.models import PodcastScript
    with open(script_path) as f:
        script = PodcastScript.model_validate(json.load(f))

    logger.info("[5/5] Generating audio from saved script (%d turns)...", len(script.turns))
    audio_path, total_chars, tts_provider_used, segments = await voice_agent.run(script)
    logger.info("[5/5] Done — %s", audio_path)
    return audio_path, total_chars, tts_provider_used, segments


async def run_pipeline(
    query: QueryParameters,
    episode_id: str,
    voice_provider: str | None = None,
    warning_capture: "_WarningCapture | None" = None,
    on_stage_start: "None | object" = None,
) -> tuple[Episode, TokenUsage, int, str, dict[str, float]]:
    """Execute the full pipeline and return (episode, token_usage, tts_chars, stage_times)."""
    from agents import bibliography_agent, fetcher_agent, graph_agent, script_agent, voice_agent

    if voice_provider:
        voice_agent.VOICE_PROVIDER = voice_provider
        logger.info("Voice provider overridden to: %s", voice_provider)

    total_usage = TokenUsage()
    stage_times: dict[str, float] = {}

    def _mark(stage: str, t_start: float) -> None:
        stage_times[stage] = time.time() - t_start

    # Step 1: Fetch papers
    logger.info("[1/5] Fetching papers...")
    t = time.time()
    papers = await fetcher_agent.run(query, episode_id)
    if not papers:
        raise RuntimeError("No papers returned — check your query parameters or API keys")
    _mark("fetch", t)
    logger.info("[1/5] Done (%.1fs) — %d papers", stage_times["fetch"], len(papers))

    # Step 2: Generate bibliography
    logger.info("[2/5] Generating annotated bibliography...")
    t = time.time()
    bibliography_path, bib_usage = await bibliography_agent.run(papers, query, episode_id)
    total_usage += bib_usage
    _mark("bibliography", t)
    logger.info("[2/5] Done (%.1fs) — %s", stage_times["bibliography"], bibliography_path)

    # Step 3: Build knowledge graph
    if callable(on_stage_start):
        on_stage_start("building")
    logger.info("[3/5] Building knowledge graph...")
    t = time.time()
    graph = KnowledgeGraph()
    graph, graph_usage = await graph_agent.run(papers, episode_id, graph)
    total_usage += graph_usage
    _mark("graph", t)
    logger.info("[3/5] Done (%.1fs) — %d nodes", stage_times["graph"], graph._graph.number_of_nodes())

    # Step 4: Generate podcast script
    logger.info("[4/5] Generating podcast script...")
    t = time.time()
    script, script_usage = await script_agent.run(papers, bibliography_path, graph, query, episode_id)
    total_usage += script_usage
    _mark("script", t)
    logger.info("[4/5] Done (%.1fs) — %d turns", stage_times["script"], len(script.turns))

    # Step 5: Generate audio
    logger.info("[5/5] Generating audio...")
    t = time.time()
    try:
        audio_path, tts_chars, tts_provider_used, segments = await voice_agent.run(script)
    except Exception:
        _mark("audio", t)
        # Write a partial manifest so Claude costs aren't lost on TTS failure.
        # The skip-to-audio path will merge TTS data in when audio is retried.
        _save_partial_manifest(
            episode_id=episode_id,
            query=query,
            usage=total_usage,
            stage_times=stage_times,
            voice_provider=voice_provider,
            bibliography_path=bibliography_path,
            warning_capture=warning_capture,
        )
        raise
    _mark("audio", t)
    logger.info("[5/5] Done (%.1fs) — %s", stage_times["audio"], audio_path)

    # Build and save Episode record
    script_path = DATA_DIR / "scripts" / f"{episode_id}.json"
    graph_snapshot = DATA_DIR / "graphs" / "graph_snapshot.json"
    episode = Episode(
        episode_id=episode_id,
        query=query,
        papers=papers,
        bibliography_path=bibliography_path,
        script_path=script_path,
        audio_path=audio_path,
        graph_snapshot_path=graph_snapshot,
        created_at=datetime.now(),
    )
    episode_file = DATA_DIR / "papers" / f"{episode_id}_episode.json"
    episode_file.parent.mkdir(parents=True, exist_ok=True)
    with open(episode_file, "w") as f:
        json.dump(episode.model_dump(mode="json"), f, indent=2, default=str)

    return episode, total_usage, tts_chars, tts_provider_used, stage_times, segments


def _build_manifest(
    episode_id: str,
    query: "QueryParameters",
    episode: "Episode",
    usage: "TokenUsage",
    tts_chars: int,
    tts_provider_used: str,
    tts_provider_requested: str,
    stage_times: dict[str, float],
    total_runtime: float,
    warning_capture: "_WarningCapture | None",
    segments: list[dict] | None = None,
) -> dict:
    """Build the run manifest dict. Shared by CLI main() and the async task worker."""
    claude_input_cost  = usage.input_tokens  / 1_000_000 * CLAUDE_INPUT_COST_PER_M_TOKENS
    claude_output_cost = usage.output_tokens / 1_000_000 * CLAUDE_OUTPUT_COST_PER_M_TOKENS
    claude_cost  = claude_input_cost + claude_output_cost
    tts_rate     = TTS_COST_PER_M_CHARS.get(tts_provider_used, 0.0)
    tts_cost     = tts_chars / 1_000_000 * tts_rate
    total_cost   = claude_cost + tts_cost
    return {
        "episode_id": episode_id,
        "created_at": datetime.now().isoformat(),
        "parameters": {
            "topic":                   query.topic,
            "disciplines":             query.disciplines,
            "source":                  query.source,
            "max_papers":              query.max_papers,
            "expertise_level":         query.user_profile.default_level.value,
            "voice_provider_requested": tts_provider_requested,
            "anchor_papers":           query.anchor_papers,
            "publication_start":       query.publication_date_range[0].isoformat() if query.publication_date_range else None,
            "publication_end":         query.publication_date_range[1].isoformat() if query.publication_date_range else None,
        },
        "stage_timings_seconds":       {k: round(v, 2) for k, v in stage_times.items()},
        "stage_timings_seconds_total": round(total_runtime, 2),
        "tokens": {"input": usage.input_tokens, "output": usage.output_tokens},
        "costs_usd": {
            "claude_input":  round(claude_input_cost, 4),
            "claude_output": round(claude_output_cost, 4),
            "claude_total":  round(claude_cost, 4),
            "tts":           round(tts_cost, 4),
            "total":         round(total_cost, 4),
        },
        "tts": {
            "provider_requested": tts_provider_requested,
            "provider_used":      tts_provider_used,
            "fallback_occurred":  tts_provider_used != tts_provider_requested,
            "characters":         tts_chars,
        },
        "output_files": {
            "audio":       str(episode.audio_path),
            "script":      str(episode.script_path),
            "bibliography": str(episode.bibliography_path),
            "fetch_trace": str(DATA_DIR / "traces" / f"{episode_id}_fetch.json"),
        },
        "trace_reasoning": query.trace_reasoning,
        "warnings": warning_capture.records if warning_capture else [],
        "segments": segments or [],
    }


def _persist_backends(manifest: dict, episode_id: str, files: dict) -> None:
    """Write manifest to DB and upload files to R2. Both are non-fatal."""
    import os
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        try:
            from core.db import insert_cost_event
            insert_cost_event(manifest, db_url)
        except Exception as exc:
            logger.warning("DB write failed for episode %s: %s", episode_id, exc)

    r2_account_id = os.getenv("R2_ACCOUNT_ID")
    r2_access_key = os.getenv("R2_ACCESS_KEY_ID")
    r2_secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
    r2_bucket     = os.getenv("R2_BUCKET_NAME")
    if all([r2_account_id, r2_access_key, r2_secret_key, r2_bucket]):
        try:
            from core.storage import upload_episode_files
            upload_episode_files(episode_id, files, r2_account_id, r2_access_key, r2_secret_key, r2_bucket)
        except Exception as exc:
            logger.warning("R2 upload failed for episode %s: %s", episode_id, exc)


def main() -> None:
    args = _parse_args()

    if args.skip_to_audio:
        episode_id = args.skip_to_audio
        logger.info("Resuming episode %s — audio-only mode", episode_id)
        try:
            audio_path, tts_chars, tts_provider_used, segments = asyncio.run(
                run_audio_only(episode_id, voice_provider=args.voice_provider)
            )
        except Exception as exc:
            logger.error("Audio generation failed: %s", exc, exc_info=True)
            raise SystemExit(1)
        tts_provider_requested = args.voice_provider or VOICE_PROVIDER
        tts_rate = TTS_COST_PER_M_CHARS.get(tts_provider_used, 0.0)
        tts_cost = tts_chars / 1_000_000 * tts_rate

        # Merge TTS data into an existing partial manifest, or write a TTS-only manifest.
        manifest_path = DATA_DIR / "traces" / f"{episode_id}_manifest.json"
        if manifest_path.exists():
            with open(manifest_path) as f:
                manifest = json.load(f)
            claude_cost = manifest.get("costs_usd", {}).get("claude_total", 0.0)
            manifest["partial"] = False
            manifest.pop("partial_reason", None)
            manifest["tts"] = {
                "provider_requested": tts_provider_requested,
                "provider_used": tts_provider_used,
                "fallback_occurred": tts_provider_used != tts_provider_requested,
                "characters": tts_chars,
            }
            manifest["costs_usd"]["tts"] = round(tts_cost, 4)
            manifest["costs_usd"]["total"] = round(claude_cost + tts_cost, 4)
            manifest["output_files"]["audio"] = str(audio_path)
            manifest["segments"] = segments
        else:
            manifest = {
                "episode_id": episode_id,
                "created_at": datetime.now().isoformat(),
                "tts_only": True,
                "tts": {
                    "provider_requested": tts_provider_requested,
                    "provider_used": tts_provider_used,
                    "fallback_occurred": tts_provider_used != tts_provider_requested,
                    "characters": tts_chars,
                },
                "costs_usd": {
                    "claude_input": 0.0, "claude_output": 0.0, "claude_total": 0.0,
                    "tts": round(tts_cost, 4),
                    "total": round(tts_cost, 4),
                },
                "tokens": {"input": 0, "output": 0},
                "output_files": {"audio": str(audio_path)},
            }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        _persist_backends(manifest, episode_id, {
            "audio":    audio_path,
            "manifest": manifest_path,
        })

        print("\n" + "=" * 60)
        print(f"Episode ID   : {episode_id}")
        print(f"Audio        : {audio_path}")
        print(f"TTS chars    : {tts_chars:,}  (${tts_cost:.4f})")
        print("=" * 60)
        return

    if not args.topic or not args.disciplines:
        raise SystemExit("--topic and --disciplines are required unless --skip-to-audio is used")
    _anchor_mode = bool(args.anchor_papers or args.anchor_paper_json)
    if not _anchor_mode and (not args.publication_start or not args.publication_end):
        raise SystemExit(
            "--publication-start and --publication-end are required unless "
            "--anchor-paper, --anchor-paper-json, or --skip-to-audio is used"
        )

    # Date range: explicit args take priority; anchor mode defaults to last 5 years
    pub_start = (
        date.fromisoformat(args.publication_start)
        if args.publication_start
        else date(date.today().year - 5, 1, 1)
    )
    pub_end = (
        date.fromisoformat(args.publication_end)
        if args.publication_end
        else date.today()
    )

    study_data_period = None
    if args.study_data_start and args.study_data_end:
        study_data_period = (
            date.fromisoformat(args.study_data_start),
            date.fromisoformat(args.study_data_end),
        )

    expertise_level = ExpertiseLevel(args.expertise_level)
    user_profile = UserProfile(
        expertise=[
            ExpertiseProfile(discipline=d, level=expertise_level)
            for d in args.disciplines
        ],
        default_level=expertise_level,
    )

    query = QueryParameters(
        topic=args.topic,
        disciplines=args.disciplines,
        cross_disciplinary=args.cross_disciplinary,
        focus_mode=args.focus_mode,
        publication_date_range=(pub_start, pub_end),
        study_data_period=study_data_period,
        max_papers=args.max_papers,
        include_preprints=args.include_preprints,
        user_profile=user_profile,
        source=args.source,
        crossref_publisher=args.crossref_publisher,
        anchor_papers=args.anchor_papers or [],
        anchor_paper_json=args.anchor_paper_json,
        enrich=args.enrich,
        trace_reasoning=args.trace_reasoning,
    )

    episode_id = _generate_episode_id(args.topic)
    logger.info("Starting PapersPod pipeline — episode: %s", episode_id)

    # Attach warning capture to root logger before pipeline runs
    warning_capture = _WarningCapture()
    logging.getLogger().addHandler(warning_capture)

    pipeline_start = time.time()
    try:
        episode, usage, tts_chars, tts_provider_used, stage_times, segments = asyncio.run(
            run_pipeline(query, episode_id, voice_provider=args.voice_provider, warning_capture=warning_capture)
        )
    except Exception as exc:
        logger.error("Pipeline failed: %s", exc, exc_info=True)
        raise SystemExit(1)
    finally:
        logging.getLogger().removeHandler(warning_capture)

    total_runtime = time.time() - pipeline_start
    tts_provider_requested = args.voice_provider or VOICE_PROVIDER
    manifest = _build_manifest(
        episode_id, query, episode, usage, tts_chars,
        tts_provider_used, tts_provider_requested,
        stage_times, total_runtime, warning_capture,
        segments=segments,
    )
    # Cost scalars needed for the receipt printout below
    claude_input_cost  = manifest["costs_usd"]["claude_input"]
    claude_output_cost = manifest["costs_usd"]["claude_output"]
    claude_cost        = manifest["costs_usd"]["claude_total"]
    tts_cost           = manifest["costs_usd"]["tts"]
    total_cost         = manifest["costs_usd"]["total"]

    manifest_path = DATA_DIR / "traces" / f"{episode_id}_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    _persist_backends(manifest, episode_id, {
        "audio":        episode.audio_path,
        "script":       episode.script_path,
        "bibliography": episode.bibliography_path,
        "manifest":     manifest_path,
    })

    def _fmt_time(secs: float) -> str:
        m, s = divmod(int(secs), 60)
        return f"{m}m {s:02d}s" if m else f"{s}s"

    W = 62
    print("\n" + "=" * W)
    print(f"  EPISODE RECEIPT")
    print("=" * W)
    print(f"  Episode      {episode.episode_id}")
    print(f"  Papers       {len(episode.papers)}")
    print()
    print(f"  Runtime")
    print(f"    Total        {_fmt_time(total_runtime)}")
    for stage, secs in stage_times.items():
        print(f"    {stage.capitalize():<12} {_fmt_time(secs)}")
    print()
    print(f"  Claude ({CLAUDE_MODEL})")
    print(f"    Input        {usage.input_tokens:>10,} tokens    ${claude_input_cost:.4f}")
    print(f"    Output       {usage.output_tokens:>10,} tokens    ${claude_output_cost:.4f}")
    print(f"    Subtotal                          ${claude_cost:.4f}")
    print()
    print(f"  TTS ({tts_provider_used})")
    print(f"    Characters   {tts_chars:>10,}            ${tts_cost:.4f}")
    if tts_provider_used != tts_provider_requested:
        print(f"    * Fallback: requested {tts_provider_requested}, used {tts_provider_used}")
    if tts_provider_used in ("elevenlabs", "elevenlabs_free"):
        print(f"    * ElevenLabs cost shown at PAYG rate; subscription plans vary")
    print()
    print(f"  Total cost                          ${total_cost:.4f}")
    print()
    print(f"  Output files")
    print(f"    Audio        {episode.audio_path}")
    print(f"    Script       {episode.script_path}")
    print(f"    Bibliography {episode.bibliography_path}")
    print(f"    Fetch trace  {DATA_DIR / 'traces' / f'{episode_id}_fetch.json'}")
    if query.trace_reasoning:
        print(f"    * Selection reasoning written to fetch trace")
    if warning_capture.records:
        print()
        print(f"  Warnings / Errors ({len(warning_capture.records)})")
        for rec in warning_capture.records:
            print(f"    {rec}")
    print("=" * W)


if __name__ == "__main__":
    main()
