import json
import logging
from pathlib import Path

from core import arxiv_client, openalex_client, semantic_scholar_client
from core.config import DATA_DIR
from core.models import ExpertiseLevel, Paper, QueryParameters

logger = logging.getLogger(__name__)

_SURVEY_KEYWORDS = {"survey", "review", "introduction", "overview", "tutorial", "primer"}

# Disciplines that map to OpenAlex (broad social science / humanities coverage)
_OPENALEX_DISCIPLINES = {
    "economics", "history", "sociology", "political science", "law",
    "anthropology", "philosophy", "education", "psychology",
    "communications", "labor studies", "science and technology studies",
    "sts", "cultural studies", "geography", "history of technology",
}


def _select_source(query: QueryParameters) -> str:
    """Return 'arxiv' or 'openalex' based on query.source and discipline heuristics."""
    if query.source != "auto":
        return query.source
    for d in query.disciplines:
        if d.lower().strip() in _OPENALEX_DISCIPLINES:
            return "openalex"
    return "arxiv"


def _get_expertise_level(query: QueryParameters) -> ExpertiseLevel:
    """Determine the expertise level for paper selection."""
    if not query.user_profile:
        return ExpertiseLevel.intermediate

    profile = query.user_profile
    for ep in profile.expertise:
        if ep.discipline.lower() in [d.lower() for d in query.disciplines]:
            return ep.level
    return profile.default_level


def _is_survey(paper: Paper) -> bool:
    """Return True if the paper title suggests it is a survey/review."""
    title_lower = paper.title.lower()
    return any(kw in title_lower for kw in _SURVEY_KEYWORDS)


def _sort_by_expertise(papers: list[Paper], level: ExpertiseLevel) -> list[Paper]:
    """Sort and filter papers according to expertise level heuristics."""
    if level == ExpertiseLevel.novice:
        # Surveys first, then by citation count descending
        return sorted(
            papers,
            key=lambda p: (not _is_survey(p), -(p.citation_count or 0)),
        )
    elif level == ExpertiseLevel.intermediate:
        # Sort by citation velocity descending (active, debated work)
        return sorted(papers, key=lambda p: -(p.citation_velocity or 0))
    else:
        # expert: most recent first, deprioritize surveys
        return sorted(
            papers,
            key=lambda p: (_is_survey(p), p.published_date),
            reverse=True,
        )


async def run(query: QueryParameters, episode_id: str) -> list[Paper]:
    """Fetch and enrich papers, apply expertise-level ordering, save to disk."""
    logger.info("FetcherAgent: fetching papers for episode %s", episode_id)

    source = _select_source(query)
    logger.info("FetcherAgent: using source=%s", source)

    if source == "openalex":
        papers = await openalex_client.fetch_papers(query)
    else:
        papers = await arxiv_client.fetch_papers(query)

    if not papers:
        logger.warning("FetcherAgent: no papers returned from %s", source)
        return []

    papers = await semantic_scholar_client.enrich_papers(papers)

    level = _get_expertise_level(query)
    papers = _sort_by_expertise(papers, level)
    logger.info("FetcherAgent: sorted %d papers for expertise level '%s'", len(papers), level)

    output_path = DATA_DIR / "papers" / f"{episode_id}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump([p.model_dump(mode="json") for p in papers], f, indent=2, default=str)
    logger.info("FetcherAgent: saved papers to %s", output_path)

    return papers
