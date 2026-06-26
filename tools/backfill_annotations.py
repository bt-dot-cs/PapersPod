"""
Backfill episode_papers.annotation from local bibliography markdown files.

Uses positional matching: bibliography sections are generated in the same
order as the papers list, so section[i] → papers[i] → arxiv_id.

Usage:
    cd /Users/Benjamin/Documents/Entrepreneurship/Agentic_Software/PapersPod
    set -a && source .env && set +a
    PYTHONPATH=. .venv/bin/python tools/backfill_annotations.py
"""
import json
import logging
import os
import re
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"


def parse_paper_sections(text: str) -> list[str]:
    """
    Split bibliography markdown into per-paper annotation strings.

    Structure:
        # Title
        intro paragraph
        ---
        citation line(s)
        [blank]
        annotation text
        ---
        ...

    Returns one annotation string per paper, in order.
    """
    # Split on section dividers; allow optional surrounding whitespace/newlines
    sections = re.split(r"\n---+\n", text)
    annotations: list[str] = []

    for section in sections[1:]:  # skip intro section
        section = section.strip()
        if not section:
            continue

        lines = section.splitlines()
        # Skip the citation block: one or more lines until we hit a blank line
        # Everything after the first blank line is the annotation
        past_citation = False
        annotation_lines: list[str] = []
        for line in lines:
            if not past_citation:
                if line.strip() == "":
                    past_citation = True
            else:
                annotation_lines.append(line)

        annotation = "\n".join(annotation_lines).strip()
        if annotation:
            annotations.append(annotation)

    return annotations


def main() -> None:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set")
        sys.exit(1)

    bib_files = sorted(
        p for p in (DATA_DIR / "bibliographies").glob("*.md")
    )
    logger.info("Found %d bibliography files", len(bib_files))

    total_updated = 0

    with psycopg.connect(db_url) as conn:
        for bib_path in bib_files:
            episode_id = bib_path.stem

            # Load ordered papers for this episode
            papers_path = DATA_DIR / "papers" / f"{episode_id}.json"
            if not papers_path.exists():
                logger.warning("No papers JSON for %s — skipping", episode_id)
                continue

            papers = json.loads(papers_path.read_text())
            arxiv_ids = [p["arxiv_id"] for p in papers]

            text = bib_path.read_text(encoding="utf-8")
            annotations = parse_paper_sections(text)

            if not annotations:
                logger.warning("No sections parsed from %s", bib_path.name)
                continue

            if len(annotations) != len(arxiv_ids):
                logger.warning(
                    "%s: %d annotations vs %d papers — positional match may be off",
                    episode_id, len(annotations), len(arxiv_ids),
                )

            episode_updated = 0
            for arxiv_id, annotation in zip(arxiv_ids, annotations):
                cur = conn.execute(
                    """
                    UPDATE episode_papers
                       SET annotation = %s
                     WHERE episode_id = %s AND arxiv_id = %s
                    """,
                    (annotation, episode_id, arxiv_id),
                )
                episode_updated += cur.rowcount

            total_updated += episode_updated
            logger.info("%s: updated %d/%d", episode_id, episode_updated, len(arxiv_ids))

    logger.info("Done. Total rows updated: %d", total_updated)


if __name__ == "__main__":
    main()
