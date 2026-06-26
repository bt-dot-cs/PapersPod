"""DOAJ (Directory of Open Access Journals) source client.

Searches the DOAJ article API. All indexed articles carry explicit license metadata,
making this a reliable source for commercial-mode episodes where license certainty matters.
Roughly 60-70% of DOAJ articles are CC BY or CC0 (commercial-safe).

No API key required.
"""
import logging
from datetime import date
from typing import Optional
from urllib.parse import quote

import httpx

from core.license_utils import normalize_license
from core.models import Paper, QueryParameters

logger = logging.getLogger(__name__)

_BASE_URL = "https://doaj.org/api/search/articles"


def _extract_doi(identifiers: list[dict]) -> Optional[str]:
    for ident in identifiers:
        if ident.get("type") == "doi":
            return (ident.get("id") or "").strip() or None
    return None


def _extract_license(licenses: list[dict]) -> str:
    if not licenses:
        return "unknown"
    lic_type = (licenses[0].get("type") or "").strip()
    return normalize_license(lic_type) if lic_type else "unknown"


def _parse_date(year: Optional[str], month: Optional[str]) -> Optional[date]:
    try:
        y = int(year)
        m = int(month) if month and str(month).isdigit() else 1
        return date(y, min(max(m, 1), 12), 1)
    except (ValueError, TypeError):
        return None


def _map_article_to_paper(article: dict) -> Optional[Paper]:
    bib = article.get("bibjson") or {}

    title = (bib.get("title") or "").strip()
    if not title:
        return None

    abstract = (bib.get("abstract") or "").strip()
    if not abstract:
        return None

    authors = [a["name"] for a in (bib.get("author") or []) if a.get("name")]

    doi = _extract_doi(bib.get("identifier") or [])
    article_id = article.get("id") or ""
    if doi:
        arxiv_id = f"doi:{doi}"
    elif article_id:
        arxiv_id = f"doaj:{article_id}"
    else:
        return None

    published_date = _parse_date(bib.get("year"), bib.get("month"))
    if published_date is None:
        return None

    license_str = _extract_license(bib.get("license") or [])

    return Paper(
        arxiv_id=arxiv_id,
        title=title,
        authors=authors,
        abstract=abstract,
        published_date=published_date,
        doi=doi,
        license=license_str,
    )


async def fetch_papers(query: QueryParameters) -> list[Paper]:
    """Query the DOAJ article search API and return Paper models."""
    pub_start, pub_end = query.publication_date_range
    page_size = max(query.max_papers * 5, 25)

    url = f"{_BASE_URL}/{quote(query.topic, safe='')}"
    params = {"pageSize": page_size, "sort": "score"}

    logger.info(
        "DOAJ search: topic=%r pub=%s to %s",
        query.topic, pub_start.isoformat(), pub_end.isoformat(),
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.error("DOAJ request failed: %s", exc)
        return []

    articles = data.get("results") or []
    papers: list[Paper] = []

    for article in articles:
        paper = _map_article_to_paper(article)
        if paper is None:
            continue
        if not (pub_start <= paper.published_date <= pub_end):
            continue
        papers.append(paper)
        logger.info("DOAJ fetched: %s — %s", paper.arxiv_id, paper.title[:60])

    logger.info("DOAJ: returned %d papers", len(papers))
    return papers
