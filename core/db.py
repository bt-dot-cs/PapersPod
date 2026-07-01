import json
import logging
from typing import Any

import psycopg

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Credits
# ---------------------------------------------------------------------------

SIGNUP_BONUS = 275


class InsufficientCreditsError(Exception):
    def __init__(self, balance: int, required: int) -> None:
        self.balance = balance
        self.required = required
        super().__init__(f"Insufficient credits: have {balance}, need {required}")


def _ensure_credits_row(user_id: str, conn: psycopg.Connection) -> None:
    """Insert user_credits row (balance=SIGNUP_BONUS) if absent. Records signup_bonus event."""
    cur = conn.execute(
        "INSERT INTO user_credits (user_id, balance) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (user_id, SIGNUP_BONUS),
    )
    if cur.rowcount > 0:
        conn.execute(
            "INSERT INTO credit_events (user_id, delta, event_type) VALUES (%s, %s, 'signup_bonus')",
            (user_id, SIGNUP_BONUS),
        )


def get_credit_balance(user_id: str, database_url: str) -> int:
    """Return current balance, initialising the account with a signup bonus on first call."""
    with psycopg.connect(database_url) as conn:
        _ensure_credits_row(user_id, conn)
        row = conn.execute(
            "SELECT balance FROM user_credits WHERE user_id = %s", (user_id,)
        ).fetchone()
        return row[0]


def debit_credits(
    user_id: str,
    cost: int,
    episode_id: str,
    event_type: str,
    database_url: str,
) -> int:
    """Atomically debit credits. Returns new balance. Raises InsufficientCreditsError if short."""
    with psycopg.connect(database_url) as conn:
        _ensure_credits_row(user_id, conn)
        cur = conn.execute(
            """
            UPDATE user_credits
               SET balance = balance - %s, updated_at = now()
             WHERE user_id = %s AND balance >= %s
            """,
            (cost, user_id, cost),
        )
        if cur.rowcount == 0:
            row = conn.execute(
                "SELECT balance FROM user_credits WHERE user_id = %s", (user_id,)
            ).fetchone()
            raise InsufficientCreditsError(row[0] if row else 0, cost)
        conn.execute(
            "INSERT INTO credit_events (user_id, delta, event_type, episode_id) VALUES (%s, %s, %s, %s)",
            (user_id, -cost, event_type, episode_id),
        )
        row = conn.execute(
            "SELECT balance FROM user_credits WHERE user_id = %s", (user_id,)
        ).fetchone()
        return row[0]


def grant_credits(
    user_id: str,
    delta: int,
    event_type: str,
    database_url: str,
    episode_id: str | None = None,
    metadata: dict | None = None,
) -> int:
    """Grant credits (or record 0-delta when throttled). Returns new balance."""
    with psycopg.connect(database_url) as conn:
        _ensure_credits_row(user_id, conn)
        if delta > 0:
            conn.execute(
                "UPDATE user_credits SET balance = balance + %s, updated_at = now() WHERE user_id = %s",
                (delta, user_id),
            )
        conn.execute(
            """
            INSERT INTO credit_events (user_id, delta, event_type, episode_id, metadata)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, delta, event_type, episode_id, json.dumps(metadata) if metadata else None),
        )
        row = conn.execute(
            "SELECT balance FROM user_credits WHERE user_id = %s", (user_id,)
        ).fetchone()
        return row[0]


def get_weekly_feedback_credit_count(user_id: str, database_url: str) -> int:
    """Sum of feedback credit grants (delta > 0) in the last 7 days for throttle check."""
    with psycopg.connect(database_url) as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(delta), 0)
              FROM credit_events
             WHERE user_id = %s
               AND event_type LIKE 'feedback_%%'
               AND delta > 0
               AND created_at >= now() - INTERVAL '7 days'
            """,
            (user_id,),
        ).fetchone()
        return int(row[0]) if row else 0


def get_credit_history(
    user_id: str,
    database_url: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return recent credit ledger entries for a user, newest first."""
    with psycopg.connect(database_url) as conn:
        rows = conn.execute(
            """
            SELECT id, delta, event_type, episode_id, metadata, created_at
              FROM credit_events
             WHERE user_id = %s
             ORDER BY created_at DESC
             LIMIT %s
            """,
            (user_id, limit),
        ).fetchall()
    return [
        {
            "id":         r[0],
            "delta":      r[1],
            "event_type": r[2],
            "episode_id": r[3],
            "metadata":   r[4],
            "created_at": r[5].isoformat() if r[5] else None,
        }
        for r in rows
    ]


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
                "anchor_paper":           ",".join(params.get("anchor_papers") or []) or params.get("anchor_paper"),
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
    """Return ordered list of papers with authors, annotation, and abstract snippet for an episode."""
    with psycopg.connect(database_url) as conn:
        rows = conn.execute(
            """
            SELECT p.arxiv_id, p.doi, p.title, p.authors, p.published_date,
                   ep.annotation, ep.display_order, p.abstract_snippet
              FROM episode_papers ep
              JOIN papers p ON p.arxiv_id = ep.arxiv_id
             WHERE ep.episode_id = %s
             ORDER BY ep.display_order
            """,
            (episode_id,),
        ).fetchall()

    return [
        {
            "arxiv_id":       r[0],
            "doi":            r[1],
            "title":          r[2],
            "authors":        r[3],
            "published_date": r[4].isoformat() if r[4] else None,
            "annotation":     r[5],
            "abstract_snippet": r[7],
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
    """Update episode lifecycle status. Stores manifest JSON and promotes metadata on completion."""
    import json as _json
    params = manifest.get("parameters") or {} if manifest else {}
    expertise_level = params.get("expertise_level") or None
    disciplines = params.get("disciplines") or None

    # Derive curation_level from manifest parameters
    curation_level: str | None = None
    if manifest:
        anchor_papers = params.get("anchor_papers") or []
        context_text = params.get("context_text")
        keywords = params.get("keywords") or []
        if anchor_papers and context_text:
            curation_level = "fully_guided"
        elif anchor_papers:
            curation_level = "anchor_guided"
        elif context_text:
            curation_level = "context_guided"
        elif keywords:
            curation_level = "keyword_guided"
        else:
            curation_level = "auto"

    with psycopg.connect(database_url) as conn:
        conn.execute(
            """
            UPDATE episodes SET
                status          = %s,
                completed_at    = CASE WHEN %s IN ('done', 'failed') THEN now() ELSE completed_at END,
                error           = %s,
                manifest        = %s,
                expertise_level = COALESCE(%s, expertise_level),
                disciplines     = COALESCE(%s, disciplines),
                curation_level  = COALESCE(%s, curation_level)
            WHERE episode_id = %s
            """,
            (
                status,
                status,
                error,
                _json.dumps(manifest) if manifest else None,
                expertise_level,
                disciplines,
                curation_level,
                episode_id,
            ),
        )
    logger.info("episode %s → %s", episode_id, status)


def upsert_episode_embedding(
    episode_id: str,
    target: str,
    embedding: list[float],
    model: str,
    database_url: str,
) -> None:
    """Upsert an embedding vector into episode_embeddings. target = 'paper_content' | 'episode_content'."""
    vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
    with psycopg.connect(database_url) as conn:
        conn.execute(
            """
            INSERT INTO episode_embeddings (episode_id, target, embedding, embedding_model)
            VALUES (%s, %s, %s::vector, %s)
            ON CONFLICT (episode_id, target) DO UPDATE SET
                embedding       = EXCLUDED.embedding,
                embedding_model = EXCLUDED.embedding_model,
                embedded_at     = now()
            """,
            (episode_id, target, vec_str, model),
        )
    logger.info("embedding upserted for episode %s target=%s", episode_id, target)


def get_similar_episodes(
    episode_id: str,
    target: str,
    database_url: str,
    limit: int = 10,
    expertise_level: str | None = None,
    curation_level: str | None = None,
) -> list[dict[str, Any]]:
    """Return episodes nearest to episode_id by cosine similarity on the given target embedding."""
    filters = ["e.episode_id != %(episode_id)s", "ee_ref.target = %(target)s", "ee_cand.target = %(target)s"]
    bind: dict[str, Any] = {"episode_id": episode_id, "target": target, "limit": limit}
    if expertise_level:
        filters.append("e.expertise_level = %(expertise_level)s")
        bind["expertise_level"] = expertise_level
    if curation_level:
        filters.append("e.curation_level = %(curation_level)s")
        bind["curation_level"] = curation_level

    where = " AND ".join(filters)
    sql = f"""
        SELECT e.episode_id,
               e.expertise_level,
               e.curation_level,
               e.manifest,
               1 - (ee_cand.embedding <=> ee_ref.embedding) AS similarity
          FROM episode_embeddings ee_ref
          JOIN episode_embeddings ee_cand ON ee_cand.target = ee_ref.target
          JOIN episodes e ON e.episode_id = ee_cand.episode_id
         WHERE {where}
         ORDER BY ee_cand.embedding <=> ee_ref.embedding
         LIMIT %(limit)s
    """
    with psycopg.connect(database_url) as conn:
        rows = conn.execute(sql, bind).fetchall()
    return [
        {
            "episode_id":     r[0],
            "expertise_level": r[1],
            "curation_level": r[2],
            "manifest":       r[3],
            "similarity":     float(r[4]),
        }
        for r in rows
    ]
