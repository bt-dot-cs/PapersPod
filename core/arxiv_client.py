import asyncio
import json
import logging
from datetime import date
from typing import Optional

import arxiv
import anthropic

from core.config import ANTHROPIC_API_KEY, ARXIV_RATE_LIMIT_SECONDS, CLAUDE_MODEL
from core.license_utils import normalize_license
from core.models import Paper, QueryParameters

logger = logging.getLogger(__name__)

# arXiv category codes for common disciplines
DISCIPLINE_CATEGORIES: dict[str, list[str]] = {
    "machine learning": ["cs.LG", "stat.ML"],
    "natural language processing": ["cs.CL"],
    "nlp": ["cs.CL"],
    "computer vision": ["cs.CV"],
    "artificial intelligence": ["cs.AI"],
    "neuroscience": ["q-bio.NC"],
    "biology": ["q-bio"],
    "physics": ["physics"],
    "mathematics": ["math"],
    "economics": ["econ"],
    "statistics": ["stat"],
    "robotics": ["cs.RO"],
    "systems": ["cs.SY"],
}

_STUDY_PERIOD_PROMPT = """\
Extract the temporal scope of data used in this research (not when the paper was published).
Return a JSON object: {{"start_year": <int or null>, "end_year": <int or null>}}
If no specific data period is mentioned, return {{"start_year": null, "end_year": null}}.
Abstract: {abstract}"""


def _build_keyword_terms(keywords: list[str]) -> list[str]:
    """Convert keyword/keyphrase list to arXiv abs: search terms."""
    terms = []
    for kw in keywords:
        words = kw.strip().split()
        if not words:
            continue
        if len(words) == 1:
            terms.append(f"abs:{words[0]}")
        elif len(words) <= 3:
            terms.append(f'abs:"{kw.strip()}"')
        else:
            # 4+ word phrase: decompose into individual abs: terms for API recall
            terms.extend(f"abs:{w}" for w in words if len(w) > 2)
    return terms


def build_search_query(query: QueryParameters) -> str:
    """Combine topic, discipline category codes, and keyword abs: terms into an arXiv query string."""
    # Quote the topic so multi-word phrases aren't parsed as independent OR terms by arXiv
    parts = [f'"{query.topic}"']
    categories = []
    for discipline in query.disciplines:
        key = discipline.lower().strip()
        if key in DISCIPLINE_CATEGORIES:
            categories.extend(DISCIPLINE_CATEGORIES[key])
    if categories:
        cat_filter = " OR ".join(f"cat:{c}" for c in categories)
        parts.append(f"({cat_filter})")
    if query.keywords:
        kw_terms = _build_keyword_terms(query.keywords)
        if kw_terms:
            parts.extend(kw_terms)
    return " AND ".join(parts)


def _map_result_to_paper(result: arxiv.Result) -> Paper:
    """Map an arxiv.Result object to a Paper model."""
    arxiv_id = result.entry_id.split("/abs/")[-1].split("v")[0]
    license_str = "unknown"
    for link in result.links:
        if getattr(link, "rel", "") == "license":
            license_str = normalize_license(str(link.href))
            break
    return Paper(
        arxiv_id=arxiv_id,
        title=result.title,
        authors=[str(a) for a in result.authors],
        abstract=result.summary,
        published_date=result.published.date(),
        pdf_url=result.pdf_url,
        doi=result.doi or None,
        license=license_str,
    )


async def _extract_study_period(
    abstract: str, client: anthropic.Anthropic
) -> tuple[Optional[date], Optional[date]]:
    """Call Claude to extract the temporal scope of data referenced in an abstract."""
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=100,
            messages=[{"role": "user", "content": _STUDY_PERIOD_PROMPT.format(abstract=abstract)}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        start_year = data.get("start_year")
        end_year = data.get("end_year")

        if start_year is None and end_year is None:
            logger.warning("Low-confidence study period extraction — both years are null")
            return None, None

        start = date(start_year, 1, 1) if start_year else None
        end = date(end_year, 12, 31) if end_year else None
        return start, end
    except Exception as exc:
        logger.error("Study period extraction failed: %s", exc)
        return None, None


async def fetch_papers(query: QueryParameters) -> list[Paper]:
    """Query arXiv and return a list of Paper models matching the query parameters."""
    search_query = build_search_query(query)
    logger.info("arXiv search query: %s", search_query)

    client_arxiv = arxiv.Client()
    search = arxiv.Search(
        query=search_query,
        max_results=max(query.max_papers * 4, 20),
        sort_by=arxiv.SortCriterion.Relevance,
    )

    papers: list[Paper] = []
    pub_start, pub_end = query.publication_date_range

    anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if query.study_data_period else None

    for result in client_arxiv.results(search):
        published = result.published.date()

        # Filter by publication date range
        if not (pub_start <= published <= pub_end):
            continue

        # Filter out preprints if requested (preprints have no journal_ref)
        if not query.include_preprints and not result.journal_ref:
            continue

        paper = _map_result_to_paper(result)

        # Extract study period from abstract via Claude if requested
        if query.study_data_period and anthropic_client:
            paper.study_period_start, paper.study_period_end = await _extract_study_period(
                result.summary, anthropic_client
            )

        papers.append(paper)
        logger.info("Fetched paper: %s", paper.arxiv_id)

        await asyncio.sleep(ARXIV_RATE_LIMIT_SECONDS)

    logger.info("Fetched %d papers from arXiv", len(papers))
    return papers
