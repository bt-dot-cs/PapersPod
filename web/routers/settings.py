import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.byok import deactivate_user_key, list_user_keys, store_user_key
from web.auth import require_auth

router = APIRouter(prefix="/settings", tags=["settings"])

Provider = Literal["anthropic", "openai", "gemini"]


def _db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise HTTPException(status_code=503, detail="Database not configured")
    return url


class UpsertKeyRequest(BaseModel):
    api_key: str = Field(..., min_length=10, description="Raw API key to store encrypted")


@router.put("/api-keys/{provider}")
async def upsert_api_key(
    provider: Provider,
    body: UpsertKeyRequest,
    claims: dict = Depends(require_auth),
    db_url: str = Depends(_db_url),
) -> dict:
    """Store (or replace) a BYOK API key for a given provider."""
    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    hint = store_user_key(user_id, provider, body.api_key, db_url)
    return {"provider": provider, "key_hint": hint, "active": True}


@router.delete("/api-keys/{provider}")
async def delete_api_key(
    provider: Provider,
    claims: dict = Depends(require_auth),
    db_url: str = Depends(_db_url),
) -> dict:
    """Deactivate a stored BYOK API key."""
    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    found = deactivate_user_key(user_id, provider, db_url)
    if not found:
        raise HTTPException(status_code=404, detail="No active key found for this provider")
    return {"provider": provider, "active": False}


@router.get("/api-keys")
async def list_api_keys(
    claims: dict = Depends(require_auth),
    db_url: str = Depends(_db_url),
) -> dict:
    """List all stored API key hints for the current user (keys never returned)."""
    user_id = claims.get("sub")
    if not user_id:
        return {"keys": []}
    keys = list_user_keys(user_id, db_url)
    return {"keys": keys}
