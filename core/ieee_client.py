import asyncio
import logging
from datetime import date
from typing import Optional

import httpx

from core.config import IEEE_API_KEY
from core.models import Paper, QueryParameters

logger = logging.getLogger(__name__)

_BASE_URL = "https://ieeexploreapi.ieee.org/api/v1/search/articles"
_RATE_LIMIT_SECONDS = 0.1
_MAX_RECORDS = 200  # IEEE hard cap per request


def _parse_date(date_str: str) -> Optional[date]:
    """Parse IEEE date strings (various formats: YYYY, Month YYYY, YYYY-MM-DD)."""
    if not date_str:
        return None
    # Try ISO first
    try:
        return date.fromisoformat(date_str[:10])
    except ValueError:
        pass
    # Try year-only
    parts = date_str.strip().split()
    for part in parts:
        try:
            year = int(part)
            if 1900 < year < 2100:
                return date(year, 1, 1)
        except ValueError:
            continue
    return None


def _map_article_to_paper(article: dict) -> Optional[Paper]:
    """Map an IEEE Xplore article dict to a Paper model. Returns None if required fields are missing."""
    title = (article.get("title") or "").strip()
    if not title:
        return None

    abstract = (article.get("abstract") or "").strip()
    if not abstract:
        return None

    published_date = _parse_date(article.get("publication_date") or "")
    if published_date is None:
        # Fall back to publication_year
        year = article.get("publication_year")
        published_date = date(int(year), 1, 1) if year else None
    if published_date is None:
        return None

    authors_block = article.get("authors") or {}
    author_list = authors_block.get("authors") or []
    authors = [a.get("full_name", "").strip() for a in author_list if a.get("full_name")]

    doi = article.get("doi") or ""
    article_number = article.get("article_number") or ""
    if doi:
        arxiv_id = f"doi:{doi}"
    elif article_number:
        arxiv_id = f"ieee:{article_number}"
    else:
        return None

    pdf_url = article.get("pdf_url") or None

    # IEEE API access_type: OPEN_ACCESS, FREE, LOCKED, EPHEMERA
    # OA flag confirms free access but doesn't specify CC license type
    access_type = (article.get("access_type") or "").upper()
    license_str = "unknown" if access_type == "OPEN_ACCESS" else "restricted"

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
    """Query the IEEE Xplore API and return Paper models."""
    if not IEEE_API_KEY:
        logger.error("IEEE_API_KEY not set — skipping IEEE fetch")
        return []

    pub_start, pub_end = query.publication_date_range
    max_records = min(query.max_papers * 5, _MAX_RECORDS)

    params = {
        "querytext": query.topic,
        "apikey": IEEE_API_KEY,
        "max_records": max_records,
        "start_record": 1,
        "start_year": pub_start.year,
        "end_year": pub_end.year,
        "sort_order": "desc",
        "sort_field": "relevance",
        "format": "json",
    }

    logger.info(
        "IEEE search: topic=%r pub=%d to %d",
        query.topic, pub_start.year, pub_end.year,
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(_BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.error("IEEE request failed: %s", exc)
        return []

    articles = data.get("articles") or []
    papers: list[Paper] = []

    for article in articles:
        paper = _map_article_to_paper(article)
        if paper is None:
            continue

        if not (pub_start <= paper.published_date <= pub_end):
            continue

        papers.append(paper)
        logger.info("IEEE fetched: %s — %s", paper.arxiv_id, paper.title[:60])

        if len(papers) >= query.max_papers:
            break

        await asyncio.sleep(_RATE_LIMIT_SECONDS)

    logger.info("IEEE: returned %d papers", len(papers))
    return papers
