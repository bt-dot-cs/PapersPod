import asyncio
import logging
import re
from datetime import date

from semanticscholar import SemanticScholar

from core.config import SEMANTIC_SCHOLAR_API_KEY
from core.models import Paper

logger = logging.getLogger(__name__)

_S2_RATE_LIMIT_SECONDS = 1.0
_FIELDS = ["citationCount", "influentialCitationCount", "tldr"]
_ANCHOR_FIELDS = [
    "paperId", "title", "abstract", "authors",
    "publicationDate", "externalIds", "citationCount", "tldr",
]
_REC_FIELDS = [
    "paperId", "title", "abstract", "authors",
    "publicationDate", "externalIds", "citationCount",
]

_ARXIV_ID_RE = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")


def _compute_citation_velocity(citation_count: int, published_date: date) -> float:
    """Citations per year since publication (minimum 1 year denominator)."""
    today = date.today()
    years = max((today - published_date).days / 365.25, 1.0)
    return round(citation_count / years, 2)


def _s2_result_to_paper(result) -> Paper | None:
    """Convert a Semantic Scholar paper result object to a Paper model."""
    if result is None:
        return None
    title = getattr(result, "title", None) or ""
    if not title:
        return None

    ext_ids = getattr(result, "externalIds", None) or {}
    arxiv_id = ext_ids.get("ArXiv") or f"s2:{result.paperId}"
    doi = ext_ids.get("DOI") or None

    authors = [
        a.name for a in (getattr(result, "authors", None) or [])
        if getattr(a, "name", None)
    ]
    abstract = getattr(result, "abstract", None) or ""

    pub_date = date.today()
    raw_date = getattr(result, "publicationDate", None)
    if raw_date:
        try:
            pub_date = date.fromisoformat(str(raw_date)[:10])
        except ValueError:
            pass

    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}" if not arxiv_id.startswith("s2:") else None

    s2_tldr = None
    tldr = getattr(result, "tldr", None)
    if tldr:
        if isinstance(tldr, dict):
            s2_tldr = tldr.get("text")
        elif hasattr(tldr, "text"):
            s2_tldr = tldr.text

    citation_count = getattr(result, "citationCount", None) or 0

    return Paper(
        arxiv_id=arxiv_id,
        title=title,
        authors=authors,
        abstract=abstract,
        published_date=pub_date,
        pdf_url=pdf_url,
        doi=doi,
        citation_count=citation_count,
        citation_velocity=_compute_citation_velocity(citation_count, pub_date),
        s2_tldr=s2_tldr,
        first_seen_date=date.today(),
    )


def _detect_id_type(identifier: str) -> str:
    """Return 'arxiv', 'doi', or 'title' based on identifier format."""
    s = identifier.strip()
    if s.lower().startswith("arxiv:") or _ARXIV_ID_RE.match(s):
        return "arxiv"
    if s.lower().startswith("doi:") or s.startswith("10."):
        return "doi"
    return "title"


def _build_s2_lookup_id(identifier: str, id_type: str) -> str:
    """Build the S2 lookup prefix string for get_paper()."""
    s = identifier.strip()
    if id_type == "arxiv":
        raw = s[6:] if s.lower().startswith("arxiv:") else s
        return f"ARXIV:{raw}"
    raw = s[4:] if s.lower().startswith("doi:") else s
    return f"DOI:{raw}"


async def fetch_anchor_and_recommendations(
    identifier: str, max_related: int
) -> tuple[Paper, list[Paper]]:
    """Resolve an anchor paper by arXiv ID, DOI, or title, then fetch related papers.

    Returns (anchor_paper, list_of_related_papers).
    """
    sch = SemanticScholar(api_key=SEMANTIC_SCHOLAR_API_KEY)
    id_type = _detect_id_type(identifier)

    # Resolve anchor
    s2_paper_id: str
    if id_type == "title":
        logger.info("AnchorPaper: searching by title — %.60s", identifier)
        results = sch.search_paper(identifier, fields=_ANCHOR_FIELDS, limit=1)
        if not results:
            raise ValueError(f"No S2 paper found for title: {identifier!r}")
        anchor = _s2_result_to_paper(results[0])
        if not anchor:
            raise ValueError(f"Could not parse anchor from title search: {identifier!r}")
        s2_paper_id = results[0].paperId
    else:
        s2_id = _build_s2_lookup_id(identifier, id_type)
        logger.info("AnchorPaper: resolving %s", s2_id)
        result = sch.get_paper(s2_id, fields=_ANCHOR_FIELDS)
        anchor = _s2_result_to_paper(result)
        if not anchor:
            raise ValueError(f"Could not resolve anchor paper: {identifier!r}")
        s2_paper_id = result.paperId

    logger.info("AnchorPaper: resolved to '%.70s'", anchor.title)

    # Fetch related papers via recommendations, fall back to title search
    related: list[Paper] = []
    try:
        recs = sch.get_recommended_papers(
            s2_paper_id, fields=_REC_FIELDS, limit=max_related * 2
        )
        for rec in recs:
            p = _s2_result_to_paper(rec)
            if p and p.abstract and p.arxiv_id != anchor.arxiv_id:
                related.append(p)
            if len(related) >= max_related:
                break
        logger.info("AnchorPaper: %d related papers via recommendations", len(related))
    except Exception as exc:
        logger.warning("AnchorPaper: recommendations unavailable (%s) — falling back to title search", exc)
        try:
            results = sch.search_paper(anchor.title, fields=_ANCHOR_FIELDS, limit=max_related * 2)
            for r in results:
                p = _s2_result_to_paper(r)
                if p and p.abstract and p.arxiv_id != anchor.arxiv_id:
                    related.append(p)
                if len(related) >= max_related:
                    break
            logger.info("AnchorPaper: %d related papers via title fallback", len(related))
        except Exception as exc2:
            logger.warning("AnchorPaper: fallback search also failed: %s", exc2)

    await asyncio.sleep(_S2_RATE_LIMIT_SECONDS)
    return anchor, related


async def fetch_recommendations_for_paper(
    anchor: Paper, max_related: int
) -> list[Paper]:
    """Fetch related papers for a pre-loaded anchor Paper (e.g. from JSON sidecar).

    Primary path (when anchor.pdf_url is set):
      1. Extract references from the PDF via Claude document API.
      2. Resolve each reference title via S2 title search.
      3. Filter to papers with abstracts; rank by citation count desc, then recency desc.

    Falls back to S2 recommendations → title search if PDF extraction yields < 2 results.
    """
    from core import pdf_reference_extractor

    sch = SemanticScholar(api_key=SEMANTIC_SCHOLAR_API_KEY)
    related: list[Paper] = []

    # --- Primary path: PDF citation extraction ---
    if anchor.pdf_url:
        logger.info("AnchorJSON: PDF extraction path — %s", anchor.pdf_url)
        refs = await pdf_reference_extractor.extract_references(anchor)
        if refs:
            candidates: list[Paper] = []
            for ref in refs:
                title = ref.get("title", "").strip()
                if not title:
                    continue
                try:
                    results = sch.search_paper(title, fields=_ANCHOR_FIELDS, limit=1)
                    await asyncio.sleep(_S2_RATE_LIMIT_SECONDS)
                    if results:
                        p = _s2_result_to_paper(results[0])
                        if p and p.abstract and p.arxiv_id != anchor.arxiv_id:
                            candidates.append(p)
                except Exception as exc:
                    logger.warning("AnchorJSON: S2 lookup failed for ref '%s': %s", title[:60], exc)

            logger.info("AnchorJSON: %d candidates resolved from PDF references", len(candidates))

            # Rank: citation count desc, then published_date desc (newest first)
            candidates.sort(
                key=lambda p: (-(p.citation_count or 0), -p.published_date.toordinal()),
            )
            # Deduplicate by arxiv_id
            seen: set[str] = set()
            for p in candidates:
                if p.arxiv_id not in seen:
                    seen.add(p.arxiv_id)
                    related.append(p)
                if len(related) >= max_related:
                    break

            if len(related) >= 2:
                logger.info("AnchorJSON: %d related papers via PDF citation extraction", len(related))
                return related

        logger.info(
            "AnchorJSON: PDF extraction yielded %d papers (< 2) — falling back to S2", len(related)
        )
        related = []

    # --- Fallback: S2 recommendations → title search ---
    s2_paper_id: str | None = None
    try:
        results = sch.search_paper(anchor.title, fields=_ANCHOR_FIELDS, limit=1)
        if results:
            s2_paper_id = results[0].paperId
            logger.info("AnchorJSON: S2 resolved anchor by title to paperId=%s", s2_paper_id)
    except Exception as exc:
        logger.warning("AnchorJSON: S2 title lookup failed (%s); will use title search for related", exc)

    if s2_paper_id:
        try:
            recs = sch.get_recommended_papers(s2_paper_id, fields=_REC_FIELDS, limit=max_related * 2)
            for rec in recs:
                p = _s2_result_to_paper(rec)
                if p and p.abstract and p.arxiv_id != anchor.arxiv_id:
                    related.append(p)
                if len(related) >= max_related:
                    break
            logger.info("AnchorJSON: %d related papers via S2 recommendations", len(related))
        except Exception as exc:
            logger.warning("AnchorJSON: recommendations unavailable (%s) — falling back to title search", exc)
            s2_paper_id = None

    if not s2_paper_id or not related:
        try:
            results = sch.search_paper(anchor.title, fields=_ANCHOR_FIELDS, limit=max_related * 2)
            for r in results:
                p = _s2_result_to_paper(r)
                if p and p.abstract and p.arxiv_id != anchor.arxiv_id:
                    related.append(p)
                if len(related) >= max_related:
                    break
            logger.info("AnchorJSON: %d related papers via title search fallback", len(related))
        except Exception as exc2:
            logger.warning("AnchorJSON: title search also failed: %s", exc2)

    await asyncio.sleep(_S2_RATE_LIMIT_SECONDS)
    return related


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
