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

from core.config import DATA_DIR
from core.knowledge_graph import KnowledgeGraph
from core.models import (
    Episode,
    ExpertiseLevel,
    ExpertiseProfile,
    QueryParameters,
    UserProfile,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _generate_episode_id(topic: str) -> str:
    """Format: {YYYY-MM-DD}_{slugified-topic}_{4-char-hex}"""
    today = date.today().isoformat()
    slug = topic.lower().strip().replace(" ", "-")[:40]
    suffix = uuid.uuid4().hex[:4]
    return f"{today}_{slug}_{suffix}"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PapersPod — research podcast generator")
    parser.add_argument("--topic", required=True, help="Primary search topic")
    parser.add_argument(
        "--disciplines", required=True, nargs="+",
        help="Disciplines to search (e.g. 'machine learning' 'neuroscience')"
    )
    parser.add_argument(
        "--focus-mode", choices=["depth", "breadth"], default="breadth",
        help="depth = methodological focus, breadth = landscape sweep"
    )
    parser.add_argument(
        "--publication-start", required=True,
        help="Publication date range start (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--publication-end", required=True,
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
    return parser.parse_args()


async def run_pipeline(query: QueryParameters, episode_id: str) -> Episode:
    """Execute the full pipeline and return an Episode record."""
    from agents import bibliography_agent, fetcher_agent, graph_agent, script_agent, voice_agent

    t0 = time.time()

    def elapsed() -> str:
        return f"{time.time() - t0:.1f}s"

    # Step 1: Fetch papers
    logger.info("[1/5] Fetching papers...")
    papers = await fetcher_agent.run(query, episode_id)
    if not papers:
        raise RuntimeError("No papers returned — check your query parameters or API keys")
    logger.info("[1/5] Done (%s) — %d papers", elapsed(), len(papers))

    # Step 2: Generate bibliography
    logger.info("[2/5] Generating annotated bibliography...")
    bibliography_path = await bibliography_agent.run(papers, query, episode_id)
    logger.info("[2/5] Done (%s) — %s", elapsed(), bibliography_path)

    # Step 3: Build knowledge graph
    logger.info("[3/5] Building knowledge graph...")
    graph = KnowledgeGraph()
    graph = await graph_agent.run(papers, episode_id, graph)
    logger.info("[3/5] Done (%s) — %d nodes", elapsed(), graph._graph.number_of_nodes())

    # Step 4: Generate podcast script
    logger.info("[4/5] Generating podcast script...")
    script = await script_agent.run(papers, bibliography_path, graph, query, episode_id)
    logger.info("[4/5] Done (%s) — %d turns", elapsed(), len(script.turns))

    # Step 5: Generate audio
    logger.info("[5/5] Generating audio...")
    audio_path = await voice_agent.run(script)
    logger.info("[5/5] Done (%s) — %s", elapsed(), audio_path)

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

    return episode


def main() -> None:
    args = _parse_args()

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
        publication_date_range=(
            date.fromisoformat(args.publication_start),
            date.fromisoformat(args.publication_end),
        ),
        study_data_period=study_data_period,
        max_papers=args.max_papers,
        include_preprints=args.include_preprints,
        user_profile=user_profile,
    )

    episode_id = _generate_episode_id(args.topic)
    logger.info("Starting PapersPod pipeline — episode: %s", episode_id)

    try:
        episode = asyncio.run(run_pipeline(query, episode_id))
    except Exception as exc:
        logger.error("Pipeline failed: %s", exc, exc_info=True)
        raise SystemExit(1)

    # Summary
    print("\n" + "=" * 60)
    print(f"Episode ID   : {episode.episode_id}")
    print(f"Papers       : {len(episode.papers)}")
    print(f"Audio        : {episode.audio_path}")
    print(f"Bibliography : {episode.bibliography_path}")
    print(f"Script       : {episode.script_path}")
    print(f"Graph nodes  : check {DATA_DIR / 'graphs' / 'graph_snapshot.json'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
