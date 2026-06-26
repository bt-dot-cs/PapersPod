"""
Backfill papers + episode_papers for existing episodes.

Reads data/papers/*.json (local disk), checks each episode exists in DB,
then upserts into papers + episode_papers tables.

Usage:
    cd /Users/Benjamin/Documents/Entrepreneurship/Agentic_Software/PapersPod
    set -a && source .env && set +a
    PYTHONPATH=. .venv/bin/python tools/backfill_papers.py
"""
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db import store_episode_papers

DATA_DIR = Path(__file__).parent.parent / "data"


def main() -> None:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set")
        sys.exit(1)

    import psycopg

    paper_files = sorted(
        p for p in (DATA_DIR / "papers").glob("*.json")
        if not p.stem.endswith("_episode")
    )
    logger.info("Found %d paper files", len(paper_files))

    with psycopg.connect(db_url) as conn:
        existing_episodes = {
            row[0]
            for row in conn.execute("SELECT episode_id FROM episodes").fetchall()
        }

    skipped = 0
    stored = 0

    for path in paper_files:
        episode_id = path.stem
        if episode_id not in existing_episodes:
            logger.warning("No DB row for episode %s — skipping", episode_id)
            skipped += 1
            continue

        try:
            papers_raw = json.loads(path.read_text())
        except Exception as exc:
            logger.error("Failed to read %s: %s", path, exc)
            continue

        if not papers_raw:
            logger.warning("Empty paper list in %s", path)
            continue

        try:
            store_episode_papers(episode_id, papers_raw, db_url)
            logger.info("Stored %d papers for %s", len(papers_raw), episode_id)
            stored += 1
        except Exception as exc:
            logger.error("Failed to store papers for %s: %s", episode_id, exc)

    logger.info("Done. Stored: %d  Skipped (no DB row): %d", stored, skipped)


if __name__ == "__main__":
    main()
