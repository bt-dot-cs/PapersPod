import asyncio
import logging
from datetime import date

from semanticscholar import SemanticScholar

from core.config import SEMANTIC_SCHOLAR_API_KEY
from core.models import Paper

logger = logging.getLogger(__name__)

_S2_RATE_LIMIT_SECONDS = 1.0
_FIELDS = ["citationCount", "influentialCitationCount", "tldr"]


def _compute_citation_velocity(citation_count: int, published_date: date) -> float:
    """Citations per year since publication (minimum 1 year denominator)."""
    today = date.today()
    years = max((today - published_date).days / 365.25, 1.0)
    return round(citation_count / years, 2)


async def enrich_papers(papers: list[Paper]) -> list[Paper]:
    """Enrich each Paper with Semantic Scholar citation data and TLDR."""
    sch = SemanticScholar(api_key=SEMANTIC_SCHOLAR_API_KEY)

    enriched: list[Paper] = []
    for paper in papers:
        try:
            result = sch.get_paper(f"ARXIV:{paper.arxiv_id}", fields=_FIELDS)

            if result is None:
                logger.warning("S2: paper not found — %s", paper.arxiv_id)
                enriched.append(paper)
                await asyncio.sleep(_S2_RATE_LIMIT_SECONDS)
                continue

            citation_count = result.citationCount or 0
            paper.citation_count = citation_count
            paper.citation_velocity = _compute_citation_velocity(citation_count, paper.published_date)

            if result.tldr and isinstance(result.tldr, dict):
                paper.s2_tldr = result.tldr.get("text")
            elif result.tldr and hasattr(result.tldr, "text"):
                paper.s2_tldr = result.tldr.text

            logger.info(
                "S2 enriched %s: %d citations, velocity=%.2f",
                paper.arxiv_id,
                citation_count,
                paper.citation_velocity,
            )
        except Exception as exc:
            logger.warning("S2 enrichment failed for %s: %s", paper.arxiv_id, exc)

        enriched.append(paper)
        await asyncio.sleep(_S2_RATE_LIMIT_SECONDS)

    return enriched
