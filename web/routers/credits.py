import os
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.db import (
    get_credit_balance,
    get_credit_history,
    get_weekly_feedback_credit_count,
    grant_credits,
)
from web.auth import require_auth

router = APIRouter(prefix="/credits", tags=["credits"])

FEEDBACK_WEEKLY_CAP = 10  # max credit points grantable via feedback per user per 7 days
FEEDBACK_AMOUNTS: dict[str, int] = {
    "bug": 5,
    "improvement": 3,
    "positive": 2,
}


def _db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise HTTPException(status_code=503, detail="Database not configured")
    return url


class CreditEventResponse(BaseModel):
    id: int
    delta: int
    event_type: str
    episode_id: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: str | None = None


class CreditsResponse(BaseModel):
    balance: int
    history: list[CreditEventResponse]


class FeedbackRequest(BaseModel):
    feedback_type: Literal["bug", "improvement", "positive"]
    content: str = Field(min_length=10, max_length=4000)


class FeedbackResponse(BaseModel):
    credits_granted: int
    new_balance: int
    throttled: bool


@router.get("", response_model=CreditsResponse)
def get_credits(claims: dict = Depends(require_auth)) -> CreditsResponse:
    user_id = claims.get("sub")
    if not user_id:
        return CreditsResponse(balance=0, history=[])
    db_url = _db_url()
    balance = get_credit_balance(user_id, db_url)
    history = get_credit_history(user_id, db_url, limit=20)
    return CreditsResponse(
        balance=balance,
        history=[CreditEventResponse(**e) for e in history],
    )


@router.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(
    body: FeedbackRequest,
    claims: dict = Depends(require_auth),
) -> FeedbackResponse:
    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required for feedback credits")
    db_url = _db_url()

    weekly_used = get_weekly_feedback_credit_count(user_id, db_url)
    reward = FEEDBACK_AMOUNTS[body.feedback_type]
    throttled = weekly_used >= FEEDBACK_WEEKLY_CAP
    granted = 0 if throttled else reward

    new_balance = grant_credits(
        user_id,
        granted,
        f"feedback_{body.feedback_type}",
        db_url,
        metadata={"content": body.content, "throttled": throttled},
    )
    return FeedbackResponse(credits_granted=granted, new_balance=new_balance, throttled=throttled)
