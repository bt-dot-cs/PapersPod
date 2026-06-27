import os
import uuid
from datetime import datetime
from typing import Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.db import (
    InsufficientCreditsError,
    create_episode,
    debit_credits,
    get_episode_papers,
    grant_credits,
    set_episode_shared,
)
from core.models import QueryParameters
from core.queue import generate_episode
from web.auth import optional_auth, require_auth

# Credit cost by curation level (matches the spec)
_CURATION_COST: dict[str, int] = {
    "auto":            1,
    "keyword_guided":  1,
    "context_guided":  2,
    "anchor_guided":   2,
    "fully_guided":    3,
}

router = APIRouter(prefix="/episodes", tags=["episodes"])


class EpisodeCreateResponse(BaseModel):
    episode_id: str
    status: str = "queued"


class EpisodeStatusResponse(BaseModel):
    episode_id: str
    status: str
    created_at: datetime
    completed_at: datetime | None = None
    error: str | None = None
    manifest: dict[str, Any] | None = None
    shared: bool = False
    is_owner: bool | None = None


class LibraryEpisodeResponse(BaseModel):
    episode_id: str
    topic: str
    created_at: datetime
    completed_at: datetime | None = None
    shared_at: datetime | None = None
    listen_count: int
    avg_completion_pct: float | None = None


class EpisodeShareRequest(BaseModel):
    shared: bool


def _db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise HTTPException(status_code=503, detail="Database not configured")
    return url


@router.get("", response_model=list[EpisodeStatusResponse])
def list_episodes(
    status: str | None = None,
    limit: int = 50,
    claims: dict = Depends(require_auth),
) -> list[EpisodeStatusResponse]:
    db_url = _db_url()
    user_id = claims.get("sub")
    with psycopg.connect(db_url) as conn:
        if status:
            rows = conn.execute(
                "SELECT episode_id, status, created_at, completed_at, error, manifest, shared "
                "FROM episodes WHERE user_id = %s AND status = %s ORDER BY created_at DESC LIMIT %s",
                (user_id, status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT episode_id, status, created_at, completed_at, error, manifest, shared "
                "FROM episodes WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
                (user_id, limit),
            ).fetchall()
    return [
        EpisodeStatusResponse(
            episode_id=r[0], status=r[1], created_at=r[2],
            completed_at=r[3], error=r[4], manifest=r[5],
            shared=bool(r[6]), is_owner=True,
        )
        for r in rows
    ]


@router.post("", response_model=EpisodeCreateResponse, status_code=202)
async def create_episode_endpoint(
    query: QueryParameters,
    claims: dict = Depends(require_auth),
) -> EpisodeCreateResponse:
    db_url = _db_url()
    user_id = claims.get("sub")
    episode_id = str(uuid.uuid4())
    cost = _CURATION_COST.get(query.curation_level, 1)

    # Credit gate — skipped in local dev where user_id is None
    if user_id:
        try:
            debit_credits(user_id, cost, episode_id, "episode_generated", db_url)
        except InsufficientCreditsError as exc:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "insufficient_credits",
                    "balance": exc.balance,
                    "required": exc.required,
                },
            )

    try:
        create_episode(episode_id, db_url, user_id=user_id)
        await generate_episode.defer_async(
            query_dict=query.model_dump(mode="json"),
            episode_id=episode_id,
        )
    except Exception:
        if user_id:
            grant_credits(user_id, cost, "refund", db_url, episode_id=episode_id)
        raise

    return EpisodeCreateResponse(episode_id=episode_id)


# /library must be defined before /{episode_id} so FastAPI doesn't match "library" as an ID
@router.get("/library", response_model=list[LibraryEpisodeResponse])
def get_library(limit: int = 50) -> list[LibraryEpisodeResponse]:
    db_url = _db_url()
    with psycopg.connect(db_url) as conn:
        rows = conn.execute(
            """
            SELECT
                e.episode_id,
                COALESCE(e.manifest->'parameters'->>'topic', e.episode_id) AS topic,
                e.created_at,
                e.completed_at,
                e.shared_at,
                COUNT(DISTINCT pe.session_id) AS listen_count,
                AVG(pe.completion_pct)         AS avg_completion_pct
            FROM episodes e
            LEFT JOIN play_events pe ON pe.episode_id = e.episode_id
            WHERE e.shared = TRUE AND e.status = 'done'
            GROUP BY e.episode_id, e.created_at, e.completed_at, e.shared_at
            ORDER BY listen_count DESC, e.shared_at DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    return [
        LibraryEpisodeResponse(
            episode_id=r[0],
            topic=r[1],
            created_at=r[2],
            completed_at=r[3],
            shared_at=r[4],
            listen_count=int(r[5]) if r[5] else 0,
            avg_completion_pct=float(r[6]) if r[6] is not None else None,
        )
        for r in rows
    ]


@router.get("/{episode_id}", response_model=EpisodeStatusResponse)
async def get_episode(
    episode_id: str,
    claims: dict | None = Depends(optional_auth),
) -> EpisodeStatusResponse:
    db_url = _db_url()
    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT episode_id, status, created_at, completed_at, error, manifest, shared, user_id "
            "FROM episodes WHERE episode_id = %s",
            (episode_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Episode not found")

    ep_id, status, created_at, completed_at, error, manifest, shared, row_user_id = row

    is_owner: bool | None = None
    if claims is not None:
        caller_sub = claims.get("sub")
        is_owner = (row_user_id == caller_sub)

    return EpisodeStatusResponse(
        episode_id=ep_id,
        status=status,
        created_at=created_at,
        completed_at=completed_at,
        error=error,
        manifest=manifest,
        shared=bool(shared),
        is_owner=is_owner,
    )


@router.patch("/{episode_id}/share", status_code=204)
def share_episode(
    episode_id: str,
    body: EpisodeShareRequest,
    claims: dict = Depends(require_auth),
) -> None:
    user_id = claims.get("sub")
    db_url = _db_url()
    updated = set_episode_shared(episode_id, body.shared, user_id, db_url)
    if not updated:
        raise HTTPException(status_code=404, detail="Episode not found or not owned by you")


@router.get("/{episode_id}/related", response_model=list[LibraryEpisodeResponse])
def get_related_episodes(
    episode_id: str,
    limit: int = 5,
) -> list[LibraryEpisodeResponse]:
    db_url = _db_url()
    with psycopg.connect(db_url) as conn:
        src = conn.execute(
            "SELECT script_embedding FROM episodes WHERE episode_id = %s",
            (episode_id,),
        ).fetchone()
        if src is None:
            raise HTTPException(status_code=404, detail="Episode not found")
        if src[0] is None:
            return []

        emb_str = str(src[0])
        rows = conn.execute(
            """
            SELECT episode_id, topic, created_at, completed_at, shared_at, listen_count, avg_completion_pct
            FROM (
                SELECT
                    e.episode_id,
                    COALESCE(e.manifest->'parameters'->>'topic', e.episode_id) AS topic,
                    e.created_at,
                    e.completed_at,
                    e.shared_at,
                    COUNT(DISTINCT pe.session_id) AS listen_count,
                    AVG(pe.completion_pct)         AS avg_completion_pct,
                    (e.script_embedding <=> %s::vector) AS distance
                FROM episodes e
                LEFT JOIN play_events pe ON pe.episode_id = e.episode_id
                WHERE e.shared = TRUE
                  AND e.status = 'done'
                  AND e.episode_id != %s
                  AND e.script_embedding IS NOT NULL
                GROUP BY e.episode_id, e.created_at, e.completed_at, e.shared_at, e.script_embedding
            ) sub
            ORDER BY distance ASC
            LIMIT %s
            """,
            (emb_str, episode_id, limit),
        ).fetchall()

    return [
        LibraryEpisodeResponse(
            episode_id=r[0],
            topic=r[1],
            created_at=r[2],
            completed_at=r[3],
            shared_at=r[4],
            listen_count=int(r[5]) if r[5] else 0,
            avg_completion_pct=float(r[6]) if r[6] is not None else None,
        )
        for r in rows
    ]


class PaperResponse(BaseModel):
    arxiv_id: str
    doi: str | None = None
    title: str
    authors: list[str]
    published_date: str | None = None
    annotation: str | None = None


@router.get("/{episode_id}/papers", response_model=list[PaperResponse])
def get_papers(episode_id: str) -> list[PaperResponse]:
    db_url = _db_url()
    rows = get_episode_papers(episode_id, db_url)
    return [PaperResponse(**r) for r in rows]


@router.get("/{episode_id}/audio-url")
def get_audio_url(episode_id: str) -> dict[str, str]:
    db_url = _db_url()
    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT status FROM episodes WHERE episode_id = %s",
            (episode_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Episode not found")
    if row[0] != "done":
        raise HTTPException(status_code=409, detail=f"Episode is '{row[0]}', audio not yet available")

    account_id  = os.getenv("R2_ACCOUNT_ID")
    access_key  = os.getenv("R2_ACCESS_KEY_ID")
    secret_key  = os.getenv("R2_SECRET_ACCESS_KEY")
    bucket      = os.getenv("R2_BUCKET_NAME")
    if not all([account_id, access_key, secret_key, bucket]):
        raise HTTPException(status_code=503, detail="Object storage not configured")

    from core.storage import get_presigned_audio_url
    url = get_presigned_audio_url(episode_id, account_id, access_key, secret_key, bucket)
    return {"url": url}
