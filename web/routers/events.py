import os
from typing import Optional

import psycopg
from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel

router = APIRouter(prefix="/events", tags=["events"])


class PlayEventRequest(BaseModel):
    episode_id: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    event_type: str  # play | pause | complete | seek
    completion_pct: Optional[float] = None


class DoiEventRequest(BaseModel):
    doi: str
    episode_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    referrer: Optional[str] = None


@router.post("/play", status_code=204)
def record_play_event(req: PlayEventRequest) -> Response:
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        with psycopg.connect(db_url) as conn:
            conn.execute(
                "INSERT INTO play_events "
                "(episode_id, user_id, session_id, event_type, completion_pct) "
                "VALUES (%s, %s, %s, %s, %s)",
                (req.episode_id, req.user_id, req.session_id, req.event_type, req.completion_pct),
            )
    return Response(status_code=204)


@router.post("/doi", status_code=204)
def record_doi_event(req: DoiEventRequest) -> Response:
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        with psycopg.connect(db_url) as conn:
            conn.execute(
                "INSERT INTO doi_referral_events "
                "(doi, episode_id, user_id, session_id, referrer) "
                "VALUES (%s, %s, %s, %s, %s)",
                (req.doi, req.episode_id, req.user_id, req.session_id, req.referrer),
            )
    return Response(status_code=204)
