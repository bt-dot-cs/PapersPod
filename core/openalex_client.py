import asyncio
import logging
from datetime import date
from typing import Optional

import httpx

from core.config import OPENALEX_EMAIL, OPENALEX_RATE_LIMIT_SECONDS
from core.license_utils import normalize_license
from core.models import Paper, QueryParameters

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.openalex.org/works"


def _user_agent() -> str:
    """Build User-Agent header; include email for OpenAlex polite pool if configured."""
    base = "PapersPod/1.0"
    if OPENALEX_EMAIL:
        return f"{base} (mailto:{OPENALEX_EMAIL})"
    return base


def _reconstruct_abstract(inverted_index: Optional[dict]) -> str:
    """Reconstruct plain text abstract from OpenAlex inverted index format."""
    if not inverted_index:
        return ""
    positions: dict[int, str] = {}
    for word, pos_list in inverted_index.items():
        for pos in pos_list:
            positions[pos] = word
    return " ".join(positions[i] for i in sorted(positions))


def _extract_arxiv_id(ids: Optional[dict]) -> Optional[str]:
    """Extract arXiv ID from OpenAlex ids dict, e.g. 'https://arxiv.org/abs/2301.12345' → '2301.12345'."""
    if not ids:
        return None
    arxiv_url = ids.get("arxiv")
    if not arxiv_url:
        return None
    # Strip version suffix if present
    arxiv_id = arxiv_url.replace("https://arxiv.org/abs/", "").split("v")[0]
    return arxiv_id if arxiv_id else None


def _map_result_to_paper(work: dict) -> Optional[Paper]:
    """Map an OpenAlex work dict to a Paper model. Returns None if required fields are missing."""
    title = work.get("title") or ""
    if not title.strip():
        return None

    abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))
    if not abstract.strip():
        logger.debug("Skipping work with no abstract: %s", work.get("id"))
        return None

    # Published date
    pub_date_str = work.get("publication_date")
    try:
        published_date = date.fromisoformat(pub_date_str) if pub_date_str else None
    except ValueError:
        published_date = None
    if published_date is None:
        # Fall back to publication_year
        year = work.get("publication_year")
        published_date = date(year, 1, 1) if year else None
    if published_date is None:
        return None

    # Authors
    authorships = work.get("authorships") or []
    authors = [
        a["author"]["display_name"]
        for a in authorships
        if a.get("author") and a["author"].get("display_name")
    ]

    # Paper ID: prefer arXiv ID, fall back to OpenAlex work ID
    ids = work.get("ids") or {}
    openalex_work_id = (work.get("id") or "").replace("https://openalex.org/", "")
    arxiv_id = _extract_arxiv_id(ids) or openalex_work_id

    # PDF URL: prefer OA PDF, then primary location
    oa_url = (work.get("open_access") or {}).get("oa_url")
    primary = work.get("primary_location") or {}
    pdf_url = oa_url or primary.get("pdf_url")

    oa_info = work.get("open_access") or {}
    license_str = normalize_license(oa_info.get("license") or "")

    doi_raw = ids.get("doi") or ""
    doi = doi_raw.replace("https://doi.org/", "").replace("http://doi.org/", "") or None

    return Paper(
        arxiv_id=arxiv_id,
        openalex_id=openalex_work_id,
        title=title.strip(),
        authors=authors,
        abstract=abstract,
        published_date=published_date,
        pdf_url=pdf_url,
        doi=doi,
        citation_count=work.get("cited_by_count"),
        license=license_str,
    )


async def fetch_papers(query: QueryParameters) -> list[Paper]:
    """Query OpenAlex and return a list of Paper models matching the query parameters."""
    pub_start, pub_end = query.publication_date_range
    per_page = max(query.max_papers * 10, 50)

    params = {
        "search": query.topic,
        "filter": f"publication_year:{pub_start.year}-{pub_end.year}",
        "sort": "relevance_score:desc",
        "per_page": per_page,
    }

    headers = {"User-Agent": _user_agent()}
    logger.info("OpenAlex search: topic=%r filter=publication_year:%d-%d", query.topic, pub_start.year, pub_end.year)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(_BASE_URL, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.error("OpenAlex request failed: %s", exc)
        return []

    works = data.get("results") or []
    papers: list[Paper] = []

    for work in works:
        paper = _map_result_to_paper(work)
        if paper is None:
            continue

        # Python-side date filter (OpenAlex year filter is approximate)
        if not (pub_start <= paper.published_date <= pub_end):
            continue

        papers.append(paper)
        logger.info("OpenAlex fetched: %s — %s", paper.arxiv_id, paper.title[:60])

        if len(papers) >= query.max_papers:
            break

        await asyncio.sleep(OPENALEX_RATE_LIMIT_SECONDS)

    logger.info("OpenAlex: returned %d papers", len(papers))
    return papers
