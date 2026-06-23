import os
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.db import get_cost_events
from web.auth import require_auth

router = APIRouter(prefix="/admin", tags=["admin"])


class CostEventResponse(BaseModel):
    episode_id: str
    created_at: str | None = None
    topic: str | None = None
    source: str | None = None
    expertise_level: str | None = None
    max_papers: int | None = None
    anchor_paper: str | None = None
    tokens_input: int | None = None
    tokens_output: int | None = None
    cost_claude_input: float | None = None
    cost_claude_output: float | None = None
    cost_claude: float | None = None
    cost_tts: float | None = None
    cost_total: float | None = None
    tts_provider_requested: str | None = None
    tts_provider_used: str | None = None
    tts_fallback_occurred: bool | None = None
    tts_characters: int | None = None
    runtime_seconds: float | None = None
    warnings: Any = None


def _db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set")
    return url


@router.get("/cost-events", response_model=list[CostEventResponse])
def list_cost_events(
    limit: int = 50,
    _claims: dict = Depends(require_auth),
) -> list[CostEventResponse]:
    rows = get_cost_events(_db_url(), limit=limit)
    return [CostEventResponse(**row) for row in rows]
