import asyncio
import logging
import re
from datetime import date
from typing import Optional

import httpx

from core.config import OPENALEX_EMAIL
from core.license_utils import normalize_license
from core.models import Paper, QueryParameters

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.crossref.org/works"
_RATE_LIMIT_SECONDS = 0.1

# Crossref member IDs for major publishers
PUBLISHER_MEMBER_IDS: dict[str, str] = {
    "sage":           "179",
    "elsevier":       "78",
    "springer":       "297",
    "wiley":          "311",
    "taylor-francis": "301",
    "oxford":         "286",
    "cambridge":      "56",
    "ieee":           "263",
}

# Fields to request — reduces payload size
_SELECT_FIELDS = ",".join([
    "title", "abstract", "author", "published", "published-print",
    "published-online", "DOI", "link", "container-title", "license",
])


def _user_agent() -> str:
    """Build User-Agent for Crossref polite pool."""
    base = "PapersPod/1.0"
    if OPENALEX_EMAIL:
        return f"{base} (mailto:{OPENALEX_EMAIL})"
    return base


def _strip_jats(text: str) -> str:
    """Strip JATS XML tags from Crossref abstract strings (e.g. <jats:p>)."""
    return re.sub(r"<[^>]+>", " ", text).strip()


def _extract_pdf_url(links: list[dict]) -> Optional[str]:
    """Return PDF URL from Crossref link array, preferring application/pdf content-type."""
    pdf_links = [lnk["URL"] for lnk in links if lnk.get("content-type") == "application/pdf"]
    if pdf_links:
        return pdf_links[0]
    tdm_links = [lnk["URL"] for lnk in links if "text-mining" in lnk.get("intended-application", "")]
    return tdm_links[0] if tdm_links else None


def _map_item_to_paper(item: dict) -> Optional[Paper]:
    """Map a Crossref work item to a Paper model. Returns None if required fields are missing."""
    title_list = item.get("title") or []
    title = title_list[0].strip() if title_list else ""
    if not title:
        return None

    raw_abstract = item.get("abstract") or ""
    abstract = _strip_jats(raw_abstract)
    if not abstract:
        return None

    # Crossref date-parts: [[year, month, day]] — month/day may be absent
    pub_block = (
        item.get("published")
        or item.get("published-print")
        or item.get("published-online")
        or {}
    )
    date_parts = (pub_block.get("date-parts") or [[]])[0]
    try:
        if len(date_parts) >= 3:
            published_date = date(date_parts[0], date_parts[1], date_parts[2])
        elif len(date_parts) == 2:
            published_date = date(date_parts[0], date_parts[1], 1)
        elif len(date_parts) == 1:
            published_date = date(date_parts[0], 1, 1)
        else:
            return None
    except (ValueError, TypeError):
        return None

    authors = [
        f"{a.get('given', '')} {a.get('family', '')}".strip()
        for a in (item.get("author") or [])
        if a.get("family")
    ]

    doi = item.get("DOI") or ""
    if not doi:
        return None
    arxiv_id = f"doi:{doi}"  # canonical dedup key for non-arXiv papers

    pdf_url = _extract_pdf_url(item.get("link") or [])

    license_entries = item.get("license") or []
    license_str = "unknown"
    for entry in license_entries:
        url = entry.get("URL") or ""
        if url:
            license_str = normalize_license(url)
            break

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


async def fetch_papers(query: QueryParameters, publisher: Optional[str] = None) -> list[Paper]:
    """Query Crossref for a specific publisher's papers and return Paper models.

    publisher: key from PUBLISHER_MEMBER_IDS (e.g. 'sage', 'elsevier'). Defaults to 'sage'.
    """
    pub_start, pub_end = query.publication_date_range
    per_page = max(query.max_papers * 10, 50)

    publisher_key = (publisher or query.crossref_publisher or "sage").lower().strip()
    member_id = PUBLISHER_MEMBER_IDS.get(publisher_key)
    if not member_id:
        logger.error(
            "Unknown Crossref publisher %r — valid options: %s",
            publisher_key, list(PUBLISHER_MEMBER_IDS),
        )
        return []

    crossref_filter = (
        f"member:{member_id},"
        f"has-full-text:true,"
        f"has-abstract:true,"
        f"from-pub-date:{pub_start.isoformat()},"
        f"until-pub-date:{pub_end.isoformat()}"
    )
    params: dict = {
        "query": query.topic,
        "filter": crossref_filter,
        "rows": per_page,
        "sort": "relevance",
        "select": _SELECT_FIELDS,
    }
    if OPENALEX_EMAIL:
        params["mailto"] = OPENALEX_EMAIL

    headers = {"User-Agent": _user_agent()}
    logger.info(
        "Crossref/%s (member:%s) search: topic=%r pub=%s to %s",
        publisher_key, member_id, query.topic, pub_start.isoformat(), pub_end.isoformat(),
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(_BASE_URL, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.error("Crossref request failed: %s", exc)
        return []

    items = (data.get("message") or {}).get("items") or []
    papers: list[Paper] = []

    for item in items:
        paper = _map_item_to_paper(item)
        if paper is None:
            continue

        if not (pub_start <= paper.published_date <= pub_end):
            continue

        papers.append(paper)
        logger.info("Crossref fetched: %s — %s", paper.arxiv_id, paper.title[:60])

        if len(papers) >= query.max_papers:
            break

        await asyncio.sleep(_RATE_LIMIT_SECONDS)

    logger.info("Crossref/%s: returned %d papers", publisher_key, len(papers))
    return papers
