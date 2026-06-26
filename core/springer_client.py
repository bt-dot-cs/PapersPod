import asyncio
import logging
from datetime import date
from typing import Optional

import httpx

from core.config import SPRINGER_API_KEY
from core.models import Paper, QueryParameters

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.springernature.com/meta/v2/json"
_RATE_LIMIT_SECONDS = 0.1
_PAGE_SIZE = 25  # API max is 100; keep smaller to avoid timeouts


def _parse_date(date_str: str) -> Optional[date]:
    """Parse Springer date strings (YYYY-MM-DD or YYYY-MM or YYYY)."""
    if not date_str:
        return None
    parts = date_str.split("-")
    try:
        if len(parts) >= 3:
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        elif len(parts) == 2:
            return date(int(parts[0]), int(parts[1]), 1)
        else:
            return date(int(parts[0]), 1, 1)
    except (ValueError, IndexError):
        return None


def _map_record_to_paper(record: dict) -> Optional[Paper]:
    """Map a Springer Nature meta record to a Paper model. Returns None if required fields are missing."""
    title = (record.get("title") or "").strip()
    if not title:
        return None

    abstract = (record.get("abstract") or "").strip()
    if not abstract:
        return None

    published_date = _parse_date(record.get("publicationDate") or "")
    if published_date is None:
        return None

    creators = record.get("creators") or []
    authors = [c.get("creator", "").strip() for c in creators if c.get("creator")]

    doi = record.get("doi") or ""
    if not doi:
        return None
    arxiv_id = f"doi:{doi}"

    # Springer OA PDF: use openaccess flag + url field
    url_field = record.get("url") or []
    pdf_url: Optional[str] = None
    for u in url_field:
        if isinstance(u, dict) and u.get("format") == "pdf":
            pdf_url = u.get("value")
            break

    # Springer Meta API exposes openaccess flag but not the specific CC license type
    openaccess = record.get("openaccess") in (True, "true", "True")
    license_str = "unknown" if openaccess else "restricted"

    return Paper(
        arxiv_id=arxiv_id,
        title=title,
        authors=authors,
        abstract=abstract,
        published_date=published_date,
        pdf_url=pdf_url,
        doi=doi or None,
        license=license_str,
    )


async def fetch_papers(query: QueryParameters) -> list[Paper]:
    """Query the Springer Nature Meta API and return Paper models."""
    if not SPRINGER_API_KEY:
        logger.error("SPRINGER_API_KEY not set — skipping Springer fetch")
        return []

    pub_start, pub_end = query.publication_date_range

    # Springer query syntax: combine topic with date constraint
    q = f"{query.topic} date:{pub_start.year}-{pub_end.year}"

    params = {
        "q": q,
        "api_key": SPRINGER_API_KEY,
        "s": 1,
        "p": _PAGE_SIZE,
    }

    logger.info(
        "Springer search: topic=%r pub=%d to %d",
        query.topic, pub_start.year, pub_end.year,
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(_BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.error("Springer request failed: %s", exc)
        return []

    records = data.get("records") or []
    papers: list[Paper] = []

    for record in records:
        paper = _map_record_to_paper(record)
        if paper is None:
            continue

        if not (pub_start <= paper.published_date <= pub_end):
            continue

        papers.append(paper)
        logger.info("Springer fetched: %s — %s", paper.arxiv_id, paper.title[:60])

        if len(papers) >= query.max_papers:
            break

        await asyncio.sleep(_RATE_LIMIT_SECONDS)

    logger.info("Springer: returned %d papers", len(papers))
    return papers
