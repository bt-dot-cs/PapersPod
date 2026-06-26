import logging
import os
from pathlib import Path

import anthropic
import psycopg

from core.config import ANTHROPIC_API_KEY, CLAUDE_HAIKU_MODEL, CLAUDE_MODEL, DATA_DIR
from core.models import ExpertiseLevel, Paper, QueryParameters, TokenUsage

logger = logging.getLogger(__name__)

_ANNOTATION_PROMPT = """\
You are generating an annotated bibliography entry for a research podcast.

Paper: {title}
Authors: {authors}
Published: {published_date}
Abstract: {abstract}
Citation count: {citation_count}
TLDR: {s2_tldr}

User expertise level for {discipline}: {expertise_level}

Write an annotated bibliography entry with:
1. Full citation (APA format)
2. 2–3 sentence annotation adapted to the user's expertise level:
   - novice: explain what the paper does in plain language, why it matters, define key terms
   - intermediate: focus on methodology and key findings, note debates it engages with
   - expert: focus on novel contributions, limitations, open questions, and how it contradicts or extends prior work

Synthesize and interpret in your own words. Do not reproduce verbatim text from the abstract.

Return only the formatted annotation text, no extra commentary.\
"""

_INTRO_PROMPT = """\
Write a 2–3 sentence introductory paragraph synthesizing the theme of a research podcast episode.

Topic: {topic}
Disciplines: {disciplines}
Focus mode: {focus_mode}
Papers covered: {paper_titles}

Keep it concise and engaging. Do not list the papers — synthesize the unifying theme. Use your own words throughout.\
"""


def _get_cached_annotation(paper_id: str, expertise_level: str, db_url: str) -> str | None:
    """Return cached annotation from paper_cache, or None on miss or error."""
    try:
        with psycopg.connect(db_url) as conn:
            row = conn.execute(
                "SELECT annotation FROM paper_cache WHERE paper_id = %s AND expertise_level = %s",
                (paper_id, expertise_level),
            ).fetchone()
            return row[0] if row else None
    except Exception as exc:
        logger.warning("paper_cache read failed: %s", exc)
        return None


def _write_cached_annotation(
    paper_id: str, expertise_level: str, annotation: str, paper: Paper, db_url: str
) -> None:
    """Write annotation to paper_cache. Non-fatal."""
    try:
        with psycopg.connect(db_url) as conn:
            conn.execute(
                """
                INSERT INTO paper_cache (paper_id, expertise_level, annotation, s2_tldr, abstract, title, model_used)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (paper_id, expertise_level) DO NOTHING
                """,
                (paper_id, expertise_level, annotation, paper.s2_tldr, paper.abstract, paper.title, CLAUDE_HAIKU_MODEL),
            )
    except Exception as exc:
        logger.warning("paper_cache write failed: %s", exc)


def _get_expertise_level(query: QueryParameters) -> ExpertiseLevel:
    if not query.user_profile:
        return ExpertiseLevel.intermediate
    for ep in query.user_profile.expertise:
        if ep.discipline.lower() in [d.lower() for d in query.disciplines]:
            return ep.level
    return query.user_profile.default_level


async def run(papers: list[Paper], query: QueryParameters, episode_id: str) -> tuple[Path, TokenUsage]:
    """Generate an annotated bibliography for the episode and save to disk."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    level = _get_expertise_level(query)
    discipline = query.disciplines[0] if query.disciplines else "general"
    usage = TokenUsage()
    db_url = os.getenv("DATABASE_URL")

    logger.info("BibliographyAgent: generating annotations for %d papers (level=%s)", len(papers), level)

    # Generate per-paper annotations
    annotations: list[str] = []
    for paper in papers:
        # Cache check — skip LLM call entirely on hit
        if db_url:
            cached = _get_cached_annotation(paper.arxiv_id, level.value, db_url)
            if cached:
                annotations.append(cached)
                logger.info("BibliographyAgent: cache hit for '%s'", paper.title[:60])
                continue

        prompt = _ANNOTATION_PROMPT.format(
            title=paper.title,
            authors=", ".join(paper.authors),
            published_date=paper.published_date.isoformat(),
            abstract=paper.abstract,
            citation_count=paper.citation_count or "N/A",
            s2_tldr=paper.s2_tldr or "N/A",
            discipline=discipline,
            expertise_level=level.value,
        )
        annotation_model = CLAUDE_HAIKU_MODEL if db_url else CLAUDE_MODEL
        response = client.messages.create(
            model=annotation_model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        usage += TokenUsage(response.usage.input_tokens, response.usage.output_tokens)
        annotation = response.content[0].text.strip()
        if db_url:
            _write_cached_annotation(paper.arxiv_id, level.value, annotation, paper, db_url)
        annotations.append(annotation)
        logger.info("BibliographyAgent: annotated '%s'", paper.title[:60])

    # Generate intro paragraph
    intro_response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": _INTRO_PROMPT.format(
                topic=query.topic,
                disciplines=", ".join(query.disciplines),
                focus_mode=query.focus_mode,
                paper_titles="; ".join(p.title for p in papers),
            ),
        }],
    )
    usage += TokenUsage(intro_response.usage.input_tokens, intro_response.usage.output_tokens)
    intro = intro_response.content[0].text.strip()

    # Assemble Markdown
    lines = [
        f"# Annotated Bibliography: {query.topic}",
        "",
        intro,
        "",
        "---",
        "",
    ]
    for annotation in annotations:
        lines.append(annotation)
        lines.append("")
        lines.append("---")
        lines.append("")

    output_path = DATA_DIR / "bibliographies" / f"{episode_id}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("BibliographyAgent: saved bibliography to %s", output_path)

    return output_path, usage
