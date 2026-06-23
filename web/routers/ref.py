import os
import re

import psycopg
from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse

from core.db import log_paper_click

router = APIRouter(prefix="/ref", tags=["ref"])

# Matches bare arxiv IDs: 2302.04542 or 2302.04542v2
_ARXIV_RE = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")


@router.get("/{identifier:path}", status_code=302)
def paper_redirect(
    identifier: str,
    episode_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
) -> RedirectResponse:
    is_arxiv = bool(_ARXIV_RE.match(identifier))
    target_url = (
        f"https://arxiv.org/abs/{identifier}"
        if is_arxiv
        else f"https://doi.org/{identifier}"
    )

    db_url = os.getenv("DATABASE_URL")
    if db_url and is_arxiv:
        try:
            log_paper_click(
                arxiv_id=identifier,
                database_url=db_url,
                episode_id=episode_id,
                user_id=user_id,
                session_id=session_id,
            )
        except Exception:
            pass  # click logging is non-fatal

    return RedirectResponse(url=target_url, status_code=302)
