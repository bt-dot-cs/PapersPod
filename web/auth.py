import json
import os
from typing import Any

import httpx
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)

# kid → JWK dict; module-level cache, refreshed on unknown kid
_jwks_cache: dict[str, Any] = {}


async def _get_jwk(kid: str) -> dict[str, Any] | None:
    if kid in _jwks_cache:
        return _jwks_cache[kid]
    jwks_url = os.environ["CLERK_JWKS_URL"]
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(jwks_url)
        resp.raise_for_status()
        data = resp.json()
    _jwks_cache.clear()
    for key in data.get("keys", []):
        _jwks_cache[key["kid"]] = key
    return _jwks_cache.get(kid)


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    """FastAPI dependency — returns JWT claims dict.

    When CLERK_JWKS_URL is unset (local dev), skips verification and returns
    {"sub": None} so routes work without a Clerk account.
    """
    if not os.getenv("CLERK_JWKS_URL"):
        return {"sub": None}

    if credentials is None:
        raise HTTPException(status_code=401, detail="Authorization header required")

    token = credentials.credentials
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Malformed token")

    kid = header.get("kid", "")
    jwk = await _get_jwk(kid)
    if jwk is None:
        raise HTTPException(status_code=401, detail="Unknown signing key")

    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")

    return payload


def _admin_ids() -> set[str]:
    raw = os.getenv("ADMIN_USER_IDS", "")
    return {s.strip() for s in raw.split(",") if s.strip()}


async def require_admin(
    claims: dict[str, Any] = Depends(require_auth),
) -> dict[str, Any]:
    """Like require_auth but also checks the caller is in ADMIN_USER_IDS.

    When CLERK_JWKS_URL is unset (local dev without auth), the gate is skipped
    so the admin panel still works locally.
    """
    if not os.getenv("CLERK_JWKS_URL"):
        return claims
    admin_ids = _admin_ids()
    sub = claims.get("sub") or ""
    if admin_ids and sub not in admin_ids:
        raise HTTPException(status_code=403, detail="Admin access required")
    return claims


async def optional_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any] | None:
    """Like require_auth but returns None (not 401) when no token is provided.

    Returns claims dict if a valid token is present, None if no Authorization
    header, or raises 401 if the token is present but invalid.
    """
    if not os.getenv("CLERK_JWKS_URL"):
        return {"sub": None}
    if credentials is None:
        return None

    token = credentials.credentials
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Malformed token")

    kid = header.get("kid", "")
    jwk = await _get_jwk(kid)
    if jwk is None:
        raise HTTPException(status_code=401, detail="Unknown signing key")

    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")

    return payload
