import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import anthropic

from core import arxiv_client, crossref_client, doaj_client, ieee_client, openalex_client, plos_client, springer_client, semantic_scholar_client, unpaywall_client
from core.config import ANTHROPIC_API_KEY, CLAUDE_HAIKU_MODEL, CLAUDE_MODEL, COMMERCIAL_MODE, DATA_DIR
from core.license_utils import is_commercial_safe
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


def _write_fetch_trace(
    episode_id: str,
    mode: str,
    source: str,
    query: QueryParameters,
    search_query_sent: str,
    candidates: list[Paper],
    selected: list[Paper],
    expertise_level: ExpertiseLevel,
    license_rejected_ids: set[str],
    commercial_mode: bool,
    unpaywall_resolved_count: int = 0,
) -> None:
    """Write fetch trace to data/traces/{episode_id}_fetch.json."""
    pub_start, pub_end = query.publication_date_range

    selected_ids = {p.arxiv_id for p in selected}
    candidate_dicts = [
        {
            "arxiv_id": p.arxiv_id,
            "title": p.title,
            "published_date": p.published_date.isoformat(),
            "citation_count": p.citation_count,
            "is_survey": _is_survey(p),
            "license": p.license,
            "selected": p.arxiv_id in selected_ids,
            "rejection_reason": (
                "license" if p.arxiv_id in license_rejected_ids
                else ("ranking" if p.arxiv_id not in selected_ids else None)
            ),
        }
        for p in candidates
    ]

    trace = {
        "episode_id": episode_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "source": source,
        "query": {
            "topic": query.topic,
            "disciplines": query.disciplines,
            "publication_start": pub_start.isoformat(),
            "publication_end": pub_end.isoformat(),
            "max_papers": query.max_papers,
        },
        "search_query_sent": search_query_sent,
        "license_filter_applied": commercial_mode,
        "unpaywall_resolved_count": unpaywall_resolved_count,
        "rejected_by_license_count": len(license_rejected_ids),
        "candidate_count": len(candidates),
        "candidates": candidate_dicts,
        "selected_count": len(selected),
        "selected_arxiv_ids": [p.arxiv_id for p in selected],
        "expertise_level_applied": expertise_level.value,
    }

    trace_path = DATA_DIR / "traces" / f"{episode_id}_fetch.json"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with open(trace_path, "w") as f:
        json.dump(trace, f, indent=2, default=str)
    logger.info("FetcherAgent: fetch trace saved to %s", trace_path)


_REASONING_PROMPT = """\
You are auditing a paper selection for a research podcast episode.

Topic: {topic}
Expertise level: {expertise_level}

Candidate pool ({candidate_count} papers, in source-returned order):
{candidates_block}

Selected papers ({selected_count} papers, in final episode order):
{selected_block}

For each selected paper write 1–2 sentences explaining why it was prioritised over the \
unselected candidates. Be specific: mention recency, citation activity, survey vs. \
original research, or direct relevance to the topic and expertise level as appropriate.

Return a JSON array only, no other text:
[{{"arxiv_id": "...", "reasoning": "..."}}, ...]"""


async def _generate_selection_reasoning(
    episode_id: str,
    query: QueryParameters,
    candidates: list[Paper],
    selected: list[Paper],
    expertise_level: ExpertiseLevel,
) -> None:
    """Call Claude to explain paper selection; append reasoning to fetch trace."""
    def _paper_line(p: Paper) -> str:
        survey_tag = " [survey]" if _is_survey(p) else ""
        citations = f" citations={p.citation_count}" if p.citation_count is not None else ""
        return f"- {p.arxiv_id}  {p.published_date}  {p.title[:80]}{survey_tag}{citations}"

    candidates_block = "\n".join(_paper_line(p) for p in candidates)
    selected_block = "\n".join(_paper_line(p) for p in selected)

    prompt = _REASONING_PROMPT.format(
        topic=query.topic,
        expertise_level=expertise_level.value,
        candidate_count=len(candidates),
        candidates_block=candidates_block,
        selected_count=len(selected),
        selected_block=selected_block,
    )

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    try:
        response = client.messages.create(
            model=CLAUDE_HAIKU_MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        reasoning = json.loads(raw.strip())
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
    except Exception as exc:
        logger.error("FetcherAgent: selection reasoning failed: %s", exc)
        return

    trace_path = DATA_DIR / "traces" / f"{episode_id}_fetch.json"
    try:
        with open(trace_path) as f:
            trace = json.load(f)
        trace["selection_reasoning"] = reasoning
        trace["selection_reasoning_tokens"] = {
            "input": input_tokens,
            "output": output_tokens,
        }
        with open(trace_path, "w") as f:
            json.dump(trace, f, indent=2, default=str)
        logger.info(
            "FetcherAgent: selection reasoning written (%d in / %d out tokens)",
            input_tokens, output_tokens,
        )
    except Exception as exc:
        logger.error("FetcherAgent: failed to append reasoning to trace: %s", exc)


def _sort_by_expertise(papers: list[Paper], level: ExpertiseLevel) -> list[Paper]:
    """Citation-based fallback sort when composite scoring is unavailable."""
    if level == ExpertiseLevel.novice:
        return sorted(papers, key=lambda p: (not _is_survey(p), -(p.citation_count or 0)))
    elif level == ExpertiseLevel.intermediate:
        return sorted(papers, key=lambda p: -(p.citation_velocity or 0))
    else:
        return sorted(papers, key=lambda p: (_is_survey(p), p.published_date), reverse=True)


async def _score_papers(
    papers: list[Paper],
    query: QueryParameters,
    level: ExpertiseLevel,
) -> list[Paper]:
    """Composite semantic scoring. Falls back to _sort_by_expertise on any error."""
    import math
    import os
    try:
        from openai import AsyncOpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set — composite scoring unavailable")

        openai_client = AsyncOpenAI(api_key=api_key)
        EMBEDDING_MODEL = "text-embedding-3-small"

        query_text = (query.context_text or query.topic)[:5_000]
        candidate_texts = [f"{p.title} {p.abstract}"[:5_000] for p in papers]

        # Single batch call: query + all candidates
        resp = await openai_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=[query_text] + candidate_texts,
        )
        query_vec = resp.data[0].embedding
        cand_vecs = [d.embedding for d in resp.data[1:]]

        # text-embedding-3-small returns unit vectors; dot product == cosine similarity
        def cosine(a: list[float], b: list[float]) -> float:
            return sum(x * y for x, y in zip(a, b))

        pub_dates = [p.published_date for p in papers]
        min_date = min(pub_dates)
        max_date = max(pub_dates)
        date_span = max(1, (max_date - min_date).days)

        long_phrases = [kw for kw in query.keywords if len(kw.split()) >= 4]

        def kw_score(paper: Paper) -> float:
            if not query.keywords:
                return 0.0
            haystack = (paper.title + " " + paper.abstract).lower()
            hits = sum(1 for kw in query.keywords if kw.lower() in haystack)
            bonus = sum(0.5 for lp in long_phrases if lp.lower() in haystack)
            return min(1.0, hits / len(query.keywords) + bonus)

        survey_weights = {
            ExpertiseLevel.novice:        0.15,
            ExpertiseLevel.intermediate:  0.0,
            ExpertiseLevel.expert:       -0.10,
        }

        scores: list[tuple[float, Paper]] = []
        for i, paper in enumerate(papers):
            sim      = cosine(query_vec, cand_vecs[i])
            kw       = kw_score(paper)
            recency  = (paper.published_date - min_date).days / date_span
            cite     = math.log1p(paper.citation_count or 0) / 10.0
            survey   = survey_weights[level] if _is_survey(paper) else 0.0
            score    = 0.60 * sim + 0.20 * kw + 0.10 * recency + 0.05 * cite + survey
            scores.append((score, paper))

        scores.sort(key=lambda x: x[0], reverse=True)
        logger.info("FetcherAgent: composite scoring complete for %d candidates", len(papers))
        return [p for _, p in scores]

    except Exception as exc:
        logger.warning("FetcherAgent: composite scoring failed (%s) — falling back to citation sort", exc)
        return _sort_by_expertise(papers, level)


async def run(query: QueryParameters, episode_id: str) -> list[Paper]:
    """Fetch and enrich papers, apply expertise-level ordering, save to disk."""
    logger.info("FetcherAgent: fetching papers for episode %s", episode_id)

    mode = "standard"
    source = "unknown"
    search_query_sent = ""
    candidates: list[Paper] = []
    license_rejected_ids: set[str] = set()
    unpaywall_resolved_count: int = 0

    if query.anchor_paper_json:
        mode = "anchor_json"
        logger.info("FetcherAgent: anchor-paper-json mode — loading from %s", query.anchor_paper_json)
        from core.models import Paper as _Paper
        with open(query.anchor_paper_json, encoding="utf-8") as _f:
            anchor = _Paper.model_validate(json.load(_f))
        logger.info("FetcherAgent: anchor loaded — '%s'", anchor.title[:70])
        related = await semantic_scholar_client.fetch_recommendations_for_paper(
            anchor, max_related=query.max_papers - 1
        )
        papers = [anchor] + related
        candidates = list(papers)
        source = "semantic_scholar"
        search_query_sent = f"anchor={anchor.arxiv_id}"
        logger.info("FetcherAgent: anchor + %d related papers", len(related))
    elif query.anchor_papers:
        mode = "anchor"
        logger.info("FetcherAgent: anchor-paper mode — %d anchor(s)", len(query.anchor_papers))
        seen_ids: set[str] = set()
        all_papers: list[Paper] = []
        max_related_per_anchor = max(query.max_papers - 1, 1)
        for ap in query.anchor_papers:
            logger.info("FetcherAgent: resolving anchor '%s'", ap[:70])
            anchor, related = await semantic_scholar_client.fetch_anchor_and_recommendations(
                ap, max_related=max_related_per_anchor
            )
            for p in [anchor] + related:
                if p.arxiv_id not in seen_ids:
                    seen_ids.add(p.arxiv_id)
                    all_papers.append(p)
        papers = all_papers
        candidates = list(papers)
        source = "semantic_scholar"
        search_query_sent = "anchor=" + ",".join(query.anchor_papers)
        logger.info("FetcherAgent: %d deduplicated papers across %d anchor(s)", len(papers), len(query.anchor_papers))
    else:
        source = _select_source(query)
        logger.info("FetcherAgent: using source=%s", source)

        if source == "openalex":
            papers = await openalex_client.fetch_papers(query)
            pub_start, pub_end = query.publication_date_range
            search_query_sent = f"topic={query.topic!r} filter=publication_year:{pub_start.year}-{pub_end.year}"
        elif source == "crossref":
            papers = await crossref_client.fetch_papers(query)
            search_query_sent = f"query={query.topic!r} publisher={query.crossref_publisher}"
        elif source == "plos":
            papers = await plos_client.fetch_papers(query)
            search_query_sent = f"q={query.topic!r}"
        elif source == "springer":
            papers = await springer_client.fetch_papers(query)
            search_query_sent = f"q={query.topic!r}"
        elif source == "ieee":
            papers = await ieee_client.fetch_papers(query)
            search_query_sent = f"querytext={query.topic!r}"
        elif source == "doaj":
            papers = await doaj_client.fetch_papers(query)
            search_query_sent = f"q={query.topic!r}"
        else:
            search_query_sent = arxiv_client.build_search_query(query)
            papers = await arxiv_client.fetch_papers(query)

        if not papers:
            logger.warning("FetcherAgent: no papers returned from %s", source)
            return []

        candidates = list(papers)

        if COMMERCIAL_MODE:
            pre_resolve = {p.arxiv_id: p.license for p in papers}
            papers = await unpaywall_client.resolve_licenses(papers)
            unpaywall_resolved_count = sum(
                1 for p in papers if p.license != pre_resolve.get(p.arxiv_id)
            )

            license_rejected_ids = {p.arxiv_id for p in papers if not is_commercial_safe(p.license)}
            for p in papers:
                if p.arxiv_id in license_rejected_ids:
                    logger.warning(
                        "FetcherAgent: [license-filter] rejected %s — license=%r",
                        p.arxiv_id, p.license,
                    )
            papers = [p for p in papers if is_commercial_safe(p.license)]
            if not papers:
                logger.warning(
                    "FetcherAgent: all %d candidates rejected by license filter (commercial mode)",
                    len(candidates),
                )
                return []
            logger.info(
                "FetcherAgent: license filter passed %d/%d candidates",
                len(papers), len(candidates),
            )

        if query.enrich:
            papers = await semantic_scholar_client.enrich_papers(papers)
            candidates = list(papers)

    level = _get_expertise_level(query)
    papers = await _score_papers(papers, query, level)
    papers = papers[:query.max_papers]
    logger.info("FetcherAgent: selected %d/%d papers for expertise level '%s'", len(papers), len(candidates), level)

    _write_fetch_trace(
        episode_id=episode_id,
        mode=mode,
        source=source,
        query=query,
        search_query_sent=search_query_sent,
        candidates=candidates,
        selected=papers,
        expertise_level=level,
        license_rejected_ids=license_rejected_ids,
        commercial_mode=COMMERCIAL_MODE,
        unpaywall_resolved_count=unpaywall_resolved_count,
    )

    if query.trace_reasoning:
        await _generate_selection_reasoning(episode_id, query, candidates, papers, level)

    output_path = DATA_DIR / "papers" / f"{episode_id}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump([p.model_dump(mode="json") for p in papers], f, indent=2, default=str)
    logger.info("FetcherAgent: saved papers to %s", output_path)

    return papers
