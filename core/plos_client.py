import asyncio
import logging
from datetime import date
from typing import Optional

import httpx

from core.models import Paper, QueryParameters

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.plos.org/search"
_RATE_LIMIT_SECONDS = 0.2  # Stay well under 10/min limit

_FIELDS = ",".join([
    "id", "title", "abstract", "author_display",
    "publication_date", "journal", "doi",
])


def _map_doc_to_paper(doc: dict) -> Optional[Paper]:
    """Map a PLOS Solr document to a Paper model. Returns None if required fields are missing."""
    title = (doc.get("title") or "").strip()
    if not title:
        return None

    abstract_raw = doc.get("abstract") or []
    abstract = " ".join(abstract_raw).strip() if isinstance(abstract_raw, list) else str(abstract_raw).strip()
    if not abstract:
        return None

    pub_date_str = doc.get("publication_date") or ""
    try:
        published_date = date.fromisoformat(pub_date_str[:10]) if pub_date_str else None
    except ValueError:
        published_date = None
    if published_date is None:
        return None

    authors = doc.get("author_display") or []

    doi = doc.get("doi") or doc.get("id") or ""
    if not doi:
        return None
    arxiv_id = f"doi:{doi}"

    # PLOS PDF URL: https://journals.plos.org/plosone/article/file?id={doi}&type=printable
    pdf_url = f"https://journals.plos.org/plosone/article/file?id={doi}&type=printable" if doi else None

    return Paper(
        arxiv_id=arxiv_id,
        title=title,
        authors=authors,
        abstract=abstract,
        published_date=published_date,
        pdf_url=pdf_url,
        doi=doi or None,
        license="cc-by",  # PLOS policy: all articles CC BY
    )


async def fetch_papers(query: QueryParameters) -> list[Paper]:
    """Query the PLOS Search API and return Paper models."""
    pub_start, pub_end = query.publication_date_range
    rows = max(query.max_papers * 5, 25)

    date_filter = (
        f"publication_date:[{pub_start.isoformat()}T00:00:00Z"
        f" TO {pub_end.isoformat()}T23:59:59Z]"
    )
    fq = f"doc_type:full AND {date_filter}"

    params = {
        "q": query.topic,
        "fq": fq,
        "fl": _FIELDS,
        "rows": rows,
        "wt": "json",
        "sort": "score desc",
    }

    logger.info(
        "PLOS search: topic=%r pub=%s to %s",
        query.topic, pub_start.isoformat(), pub_end.isoformat(),
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(_BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.error("PLOS request failed: %s", exc)
        return []

    docs = (data.get("response") or {}).get("docs") or []
    papers: list[Paper] = []

    for doc in docs:
        paper = _map_doc_to_paper(doc)
        if paper is None:
            continue

        if not (pub_start <= paper.published_date <= pub_end):
            continue

        papers.append(paper)
        logger.info("PLOS fetched: %s — %s", paper.arxiv_id, paper.title[:60])

        if len(papers) >= query.max_papers:
            break

        await asyncio.sleep(_RATE_LIMIT_SECONDS)

    logger.info("PLOS: returned %d papers", len(papers))
    return papers
