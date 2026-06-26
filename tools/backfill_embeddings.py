"""
Backfill dual embeddings for all existing episodes.

For each episode:
  - paper_content: built from Neon papers table (title + abstract_snippet)
  - episode_content: built from R2 script.json (dialogue turns concatenated)

Idempotent: skips (episode_id, target) rows that already exist in episode_embeddings
with the same embedding_model.

Usage:
    python -m tools.backfill_embeddings [--dry-run] [--target paper_content|episode_content]
"""
import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
MAX_CHARS = 30_000


def _get_all_episodes(conn: psycopg.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT episode_id, manifest FROM episodes WHERE status = 'done' ORDER BY created_at"
    ).fetchall()
    return [{"episode_id": r[0], "manifest": r[1]} for r in rows]


def _already_embedded(conn: psycopg.Connection, episode_id: str, target: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM episode_embeddings WHERE episode_id = %s AND target = %s AND embedding_model = %s",
        (episode_id, target, EMBEDDING_MODEL),
    ).fetchone()
    return row is not None


def _get_papers(conn: psycopg.Connection, episode_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT p.title, p.abstract_snippet
          FROM episode_papers ep
          JOIN papers p ON p.arxiv_id = ep.arxiv_id
         WHERE ep.episode_id = %s
         ORDER BY ep.display_order
        """,
        (episode_id,),
    ).fetchall()
    return [{"title": r[0], "abstract_snippet": r[1]} for r in rows]


def _upsert_embedding(
    conn: psycopg.Connection, episode_id: str, target: str, embedding: list[float]
) -> None:
    vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
    conn.execute(
        """
        INSERT INTO episode_embeddings (episode_id, target, embedding, embedding_model)
        VALUES (%s, %s, %s::vector, %s)
        ON CONFLICT (episode_id, target) DO UPDATE SET
            embedding       = EXCLUDED.embedding,
            embedding_model = EXCLUDED.embedding_model,
            embedded_at     = now()
        """,
        (episode_id, target, vec_str, EMBEDDING_MODEL),
    )


def _backfill_paper_content(
    conn: psycopg.Connection, openai_client: OpenAI, episode_id: str, manifest: dict, dry_run: bool
) -> bool:
    if _already_embedded(conn, episode_id, "paper_content"):
        logger.info("[%s] paper_content already exists — skipping", episode_id)
        return False

    params = manifest.get("parameters") or {}
    topic = params.get("topic", "")
    papers = _get_papers(conn, episode_id)
    if not papers:
        logger.warning("[%s] no papers found — skipping paper_content", episode_id)
        return False

    sections = [f"{p['title']}: {p.get('abstract_snippet') or ''}" for p in papers]
    text = (f"{topic}\n\n" + "\n\n".join(sections))[:MAX_CHARS]

    if dry_run:
        logger.info("[%s] DRY RUN paper_content — %d chars", episode_id, len(text))
        return False

    resp = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    _upsert_embedding(conn, episode_id, "paper_content", resp.data[0].embedding)
    logger.info("[%s] paper_content embedded", episode_id)
    return True


def _backfill_episode_content(
    conn: psycopg.Connection,
    openai_client: OpenAI,
    s3_client,
    bucket: str,
    episode_id: str,
    dry_run: bool,
) -> bool:
    if _already_embedded(conn, episode_id, "episode_content"):
        logger.info("[%s] episode_content already exists — skipping", episode_id)
        return False

    try:
        obj = s3_client.get_object(Bucket=bucket, Key=f"episodes/{episode_id}/script.json")
        script = json.loads(obj["Body"].read())
    except Exception as exc:
        logger.warning("[%s] R2 script fetch failed: %s", episode_id, exc)
        return False

    turns = script.get("turns") or []
    dialogue = " ".join(t["text"] for t in turns if t.get("text"))
    dialogue = dialogue[:MAX_CHARS]
    if not dialogue:
        logger.warning("[%s] empty dialogue — skipping episode_content", episode_id)
        return False

    if dry_run:
        logger.info("[%s] DRY RUN episode_content — %d chars", episode_id, len(dialogue))
        return False

    resp = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=dialogue)
    _upsert_embedding(conn, episode_id, "episode_content", resp.data[0].embedding)
    logger.info("[%s] episode_content embedded", episode_id)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill episode embeddings")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be embedded, don't write")
    parser.add_argument(
        "--target",
        choices=["paper_content", "episode_content", "both"],
        default="both",
        help="Which embedding target to backfill (default: both)",
    )
    args = parser.parse_args()

    db_url = os.getenv("DATABASE_URL_DIRECT") or os.getenv("DATABASE_URL")
    if not db_url:
        sys.exit("DATABASE_URL or DATABASE_URL_DIRECT not set")

    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        sys.exit("OPENAI_API_KEY not set")

    r2_account_id = os.getenv("R2_ACCOUNT_ID")
    r2_access_key = os.getenv("R2_ACCESS_KEY_ID")
    r2_secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
    r2_bucket     = os.getenv("R2_BUCKET_NAME")

    want_episode_content = args.target in ("episode_content", "both")
    if want_episode_content and not all([r2_account_id, r2_access_key, r2_secret_key, r2_bucket]):
        sys.exit("R2 env vars required for episode_content backfill")

    openai_client = OpenAI(api_key=openai_api_key)

    s3_client = None
    if want_episode_content:
        import boto3
        s3_client = boto3.client(
            "s3",
            endpoint_url=f"https://{r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=r2_access_key,
            aws_secret_access_key=r2_secret_key,
            region_name="auto",
        )

    paper_count = episode_count = 0

    with psycopg.connect(db_url) as conn:
        episodes = _get_all_episodes(conn)
        logger.info("Found %d completed episodes to process", len(episodes))

        for ep in episodes:
            episode_id = ep["episode_id"]
            manifest = ep["manifest"] or {}

            if args.target in ("paper_content", "both"):
                try:
                    if _backfill_paper_content(conn, openai_client, episode_id, manifest, args.dry_run):
                        paper_count += 1
                        time.sleep(0.1)  # gentle rate limiting
                except Exception as exc:
                    logger.error("[%s] paper_content error: %s", episode_id, exc)

            if want_episode_content:
                try:
                    if _backfill_episode_content(conn, openai_client, s3_client, r2_bucket, episode_id, args.dry_run):
                        episode_count += 1
                        time.sleep(0.1)
                except Exception as exc:
                    logger.error("[%s] episode_content error: %s", episode_id, exc)

    label = "DRY RUN" if args.dry_run else "DONE"
    logger.info("%s — paper_content: %d new, episode_content: %d new", label, paper_count, episode_count)


if __name__ == "__main__":
    main()
