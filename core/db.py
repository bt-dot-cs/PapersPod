import json
import logging
from typing import Any

import psycopg

logger = logging.getLogger(__name__)


def insert_cost_event(manifest: dict[str, Any], database_url: str) -> None:
    """Upsert one row into cost_events from a completed episode manifest."""
    params = manifest.get("parameters") or {}
    tokens = manifest.get("tokens") or {}
    costs  = manifest.get("costs_usd") or {}
    tts    = manifest.get("tts") or {}

    with psycopg.connect(database_url) as conn:
        conn.execute(
            """
            INSERT INTO cost_events (
                episode_id, created_at,
                topic, source, expertise_level, max_papers, anchor_paper,
                tokens_input, tokens_output,
                cost_claude_input, cost_claude_output, cost_claude,
                cost_tts, cost_total,
                tts_provider_requested, tts_provider_used,
                tts_fallback_occurred, tts_characters,
                runtime_seconds, trace_reasoning, warnings
            ) VALUES (
                %(episode_id)s, %(created_at)s,
                %(topic)s, %(source)s, %(expertise_level)s, %(max_papers)s, %(anchor_paper)s,
                %(tokens_input)s, %(tokens_output)s,
                %(cost_claude_input)s, %(cost_claude_output)s, %(cost_claude)s,
                %(cost_tts)s, %(cost_total)s,
                %(tts_provider_requested)s, %(tts_provider_used)s,
                %(tts_fallback_occurred)s, %(tts_characters)s,
                %(runtime_seconds)s, %(trace_reasoning)s, %(warnings)s
            )
            ON CONFLICT (episode_id) DO UPDATE SET
                tokens_input           = EXCLUDED.tokens_input,
                tokens_output          = EXCLUDED.tokens_output,
                cost_claude_input      = EXCLUDED.cost_claude_input,
                cost_claude_output     = EXCLUDED.cost_claude_output,
                cost_claude            = EXCLUDED.cost_claude,
                cost_tts               = EXCLUDED.cost_tts,
                cost_total             = EXCLUDED.cost_total,
                tts_provider_requested = EXCLUDED.tts_provider_requested,
                tts_provider_used      = EXCLUDED.tts_provider_used,
                tts_fallback_occurred  = EXCLUDED.tts_fallback_occurred,
                tts_characters         = EXCLUDED.tts_characters,
                runtime_seconds        = EXCLUDED.runtime_seconds,
                trace_reasoning        = EXCLUDED.trace_reasoning,
                warnings               = EXCLUDED.warnings
            """,
            {
                "episode_id":             manifest["episode_id"],
                "created_at":             manifest["created_at"],
                "topic":                  params.get("topic"),
                "source":                 params.get("source"),
                "expertise_level":        params.get("expertise_level"),
                "max_papers":             params.get("max_papers"),
                "anchor_paper":           params.get("anchor_paper"),
                "tokens_input":           tokens.get("input", 0),
                "tokens_output":          tokens.get("output", 0),
                "cost_claude_input":      costs.get("claude_input", 0),
                "cost_claude_output":     costs.get("claude_output", 0),
                "cost_claude":            costs.get("claude_total", 0),
                "cost_tts":               costs.get("tts", 0),
                "cost_total":             costs.get("total", 0),
                "tts_provider_requested": tts.get("provider_requested"),
                "tts_provider_used":      tts.get("provider_used"),
                "tts_fallback_occurred":  tts.get("fallback_occurred", False),
                "tts_characters":         tts.get("characters", 0),
                "runtime_seconds":        manifest.get("stage_timings_seconds_total"),
                "trace_reasoning":        manifest.get("trace_reasoning", False),
                "warnings":               json.dumps(manifest.get("warnings", [])),
            },
        )
    logger.info("cost_events upserted for episode %s", manifest["episode_id"])


def create_episode(episode_id: str, database_url: str, user_id: str | None = None) -> None:
    """Insert a new episode row with status='queued'."""
    with psycopg.connect(database_url) as conn:
        conn.execute(
            "INSERT INTO episodes (episode_id, status, user_id) VALUES (%s, 'queued', %s) ON CONFLICT DO NOTHING",
            (episode_id, user_id),
        )
    logger.info("episode created: %s", episode_id)


def store_script_embedding(episode_id: str, embedding: list[float], database_url: str) -> None:
    """Store script embedding vector for an episode (pgvector VECTOR type)."""
    vec_str = '[' + ','.join(str(v) for v in embedding) + ']'
    with psycopg.connect(database_url) as conn:
        conn.execute(
            "UPDATE episodes SET script_embedding = %s::vector WHERE episode_id = %s",
            (vec_str, episode_id),
        )
    logger.info("script_embedding stored for episode %s", episode_id)


def set_episode_shared(episode_id: str, shared: bool, user_id: str, database_url: str) -> bool:
    """Toggle shared flag; only updates if the episode belongs to user_id. Returns True if updated."""
    with psycopg.connect(database_url) as conn:
        cur = conn.execute(
            """
            UPDATE episodes
               SET shared    = %s,
                   shared_at = CASE WHEN %s THEN now() ELSE NULL END
             WHERE episode_id = %s AND user_id = %s
            """,
            (shared, shared, episode_id, user_id),
        )
    updated = cur.rowcount > 0
    logger.info("episode %s shared=%s updated=%s", episode_id, shared, updated)
    return updated


def store_episode_papers(episode_id: str, papers: list[Any], database_url: str) -> None:
    """Upsert papers and link them to an episode. Pulls annotations from paper_cache."""
    from datetime import date as _date

    with psycopg.connect(database_url) as conn:
        for order, paper in enumerate(papers):
            arxiv_id = paper.arxiv_id if hasattr(paper, "arxiv_id") else paper["arxiv_id"]
            title = paper.title if hasattr(paper, "title") else paper["title"]
            authors = paper.authors if hasattr(paper, "authors") else paper["authors"]
            doi = (paper.doi if hasattr(paper, "doi") else paper.get("doi")) or None
            pub_date = paper.published_date if hasattr(paper, "published_date") else paper.get("published_date")
            if isinstance(pub_date, str):
                try:
                    pub_date = _date.fromisoformat(pub_date)
                except (ValueError, TypeError):
                    pub_date = None
            abstract = paper.abstract if hasattr(paper, "abstract") else paper.get("abstract", "")
            snippet = (abstract or "")[:500] or None

            conn.execute(
                """
                INSERT INTO papers (arxiv_id, doi, title, authors, published_date, abstract_snippet)
                VALUES (%s, %s, %s, %s::jsonb, %s, %s)
                ON CONFLICT (arxiv_id) DO UPDATE SET
                    doi              = COALESCE(EXCLUDED.doi, papers.doi),
                    title            = EXCLUDED.title,
                    authors          = EXCLUDED.authors,
                    published_date   = COALESCE(EXCLUDED.published_date, papers.published_date),
                    abstract_snippet = COALESCE(EXCLUDED.abstract_snippet, papers.abstract_snippet)
                """,
                (arxiv_id, doi, title, json.dumps(authors), pub_date, snippet),
            )

            row = conn.execute(
                "SELECT annotation FROM paper_cache WHERE paper_id = %s LIMIT 1",
                (arxiv_id,),
            ).fetchone()
            annotation = row[0] if row else None

            conn.execute(
                """
                INSERT INTO episode_papers (episode_id, arxiv_id, annotation, display_order)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (episode_id, arxiv_id) DO NOTHING
                """,
                (episode_id, arxiv_id, annotation, order),
            )

    logger.info("stored %d papers for episode %s", len(papers), episode_id)


def log_paper_click(
    arxiv_id: str,
    database_url: str,
    episode_id: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
) -> None:
    """Record a click-through to a paper source."""
    with psycopg.connect(database_url) as conn:
        conn.execute(
            """
            INSERT INTO paper_clicks (episode_id, arxiv_id, user_id, session_id)
            VALUES (%s, %s, %s, %s)
            """,
            (episode_id, arxiv_id, user_id, session_id),
        )


def get_episode_papers(episode_id: str, database_url: str) -> list[dict[str, Any]]:
    """Return ordered list of papers with authors and annotation for an episode."""
    with psycopg.connect(database_url) as conn:
        rows = conn.execute(
            """
            SELECT p.arxiv_id, p.doi, p.title, p.authors, p.published_date,
                   ep.annotation, ep.display_order
              FROM episode_papers ep
              JOIN papers p ON p.arxiv_id = ep.arxiv_id
             WHERE ep.episode_id = %s
             ORDER BY ep.display_order
            """,
            (episode_id,),
        ).fetchall()

    return [
        {
            "arxiv_id":     r[0],
            "doi":          r[1],
            "title":        r[2],
            "authors":      r[3],
            "published_date": r[4].isoformat() if r[4] else None,
            "annotation":   r[5],
        }
        for r in rows
    ]


def get_cost_events(database_url: str, limit: int = 50) -> list[dict[str, Any]]:
    """Return recent cost_events rows, newest first."""
    with psycopg.connect(database_url) as conn:
        rows = conn.execute(
            """
            SELECT
                episode_id, created_at, topic, source, expertise_level, max_papers,
                anchor_paper, tokens_input, tokens_output,
                cost_claude_input, cost_claude_output, cost_claude,
                cost_tts, cost_total,
                tts_provider_requested, tts_provider_used,
                tts_fallback_occurred, tts_characters,
                runtime_seconds, warnings
            FROM cost_events
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "episode_id":              r[0],
            "created_at":              r[1].isoformat() if r[1] else None,
            "topic":                   r[2],
            "source":                  r[3],
            "expertise_level":         r[4],
            "max_papers":              r[5],
            "anchor_paper":            r[6],
            "tokens_input":            r[7],
            "tokens_output":           r[8],
            "cost_claude_input":       float(r[9])  if r[9]  is not None else None,
            "cost_claude_output":      float(r[10]) if r[10] is not None else None,
            "cost_claude":             float(r[11]) if r[11] is not None else None,
            "cost_tts":                float(r[12]) if r[12] is not None else None,
            "cost_total":              float(r[13]) if r[13] is not None else None,
            "tts_provider_requested":  r[14],
            "tts_provider_used":       r[15],
            "tts_fallback_occurred":   r[16],
            "tts_characters":          r[17],
            "runtime_seconds":         float(r[18]) if r[18] is not None else None,
            "warnings":                r[19],
        }
        for r in rows
    ]


def update_episode_status(
    episode_id: str,
    status: str,
    database_url: str,
    error: str | None = None,
    manifest: dict[str, Any] | None = None,
) -> None:
    """Update episode lifecycle status. Stores manifest JSON on completion."""
    import json as _json
    with psycopg.connect(database_url) as conn:
        conn.execute(
            """
            UPDATE episodes SET
                status       = %s,
                completed_at = CASE WHEN %s IN ('done', 'failed') THEN now() ELSE completed_at END,
                error        = %s,
                manifest     = %s
            WHERE episode_id = %s
            """,
            (
                status,
                status,
                error,
                _json.dumps(manifest) if manifest else None,
                episode_id,
            ),
        )
    logger.info("episode %s → %s", episode_id, status)
