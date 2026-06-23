import json
import logging
from pathlib import Path

import anthropic

from core.config import ANTHROPIC_API_KEY, CLAUDE_MODEL, COMMERCIAL_MODE, DATA_DIR
from core.knowledge_graph import KnowledgeGraph
from core.models import DialogueTurn, ExpertiseLevel, Paper, PodcastScript, QueryParameters, TokenUsage

logger = logging.getLogger(__name__)

_SCRIPT_PROMPT = """\
You are writing a podcast script for PapersPod, a research podcast.

EPISODE TOPIC: {topic}
DISCIPLINES: {disciplines}
FOCUS MODE: {focus_mode}
USER EXPERTISE: {expertise_description}

PAPERS DISCUSSED:
{papers_summary}

KNOWLEDGE GRAPH CONTEXT:
{graph_context}

ANNOTATED BIBLIOGRAPHY:
{bibliography_content}

Generate a natural, engaging two-host podcast dialogue.

HOST A (Alex): Expert explainer. Knowledgeable, precise, uses appropriate terminology for the expertise level.
HOST B (Jordan): Curious generalist. Asks clarifying questions, draws out implications, keeps the conversation accessible.

Rules:
- 800–1200 words total (approximately 6–8 minutes of audio)
- Alex must open his first turn with "Welcome to PapersPod" and introduce himself by name; he may then either (a) introduce the topic and note that Jordan is with him, or (b) introduce Jordan by name and then the topic
- Jordan must name herself or confirm her presence by name in her first turn (e.g. "I'm Jordan" or "And I'm Jordan")
- Both hosts named, show title said, and topic established within the first two turns — then open with a hook
- Cover all {n_papers} papers but weave them into a narrative, not a list
- Include at least one moment of "this paper actually contradicts what other work found"
- Close with what questions remain open
- Adapt depth to expertise level: {expertise_description}
- Synthesize and explain ideas in your own words — never reproduce verbatim sentences or passages from the source papers
- Format each turn as a JSON object on its own line (no array brackets, no commas between objects)
- For each turn include "paper_refs": a list of arXiv IDs (from the bracketed IDs in PAPERS DISCUSSED above) that are primarily discussed in that turn — use an empty list if the turn is not about a specific paper

Return ONLY a JSON array of turns:
[{{"host": "A", "text": "...", "paper_refs": ["2301.12345"]}}, {{"host": "B", "text": "...", "paper_refs": []}}, ...]

No preamble, no explanation, just the JSON array.\
"""

_DISCLAIMER_TEXT = (
    "The following is an AI-generated interpretation of peer-reviewed research. "
    "For verified data, consult the original publications linked in the show notes."
)

_EXPERTISE_DESCRIPTIONS = {
    ExpertiseLevel.novice: (
        "novice — explain concepts in plain language, use analogies, define technical terms, "
        "emphasize why this research matters to everyday life"
    ),
    ExpertiseLevel.intermediate: (
        "intermediate — assume familiarity with core concepts, focus on methodology and key debates, "
        "compare approaches across papers"
    ),
    ExpertiseLevel.expert: (
        "expert — skip basics, focus on novel contributions, limitations, open questions, "
        "contradictions with prior work, and frontier implications"
    ),
}


def _get_expertise_level(query: QueryParameters) -> ExpertiseLevel:
    if not query.user_profile:
        return ExpertiseLevel.intermediate
    for ep in query.user_profile.expertise:
        if ep.discipline.lower() in [d.lower() for d in query.disciplines]:
            return ep.level
    return query.user_profile.default_level


def _summarize_papers(papers: list[Paper]) -> str:
    lines = []
    for i, p in enumerate(papers, 1):
        tldr = p.s2_tldr or "No summary available."
        lines.append(
            f"{i}. [{p.arxiv_id}] {p.title} ({p.published_date.year})\n"
            f"   Authors: {', '.join(p.authors[:3])}\n"
            f"   Citations: {p.citation_count or 'N/A'}\n"
            f"   Summary: {tldr}"
        )
    return "\n\n".join(lines)


def _build_graph_context(graph: KnowledgeGraph, paper_ids: list[str]) -> str:
    """Extract key concepts/methods from the graph for the papers being discussed."""
    lines = []
    for arxiv_id in paper_ids:
        node_id = f"paper:{arxiv_id}"
        if node_id not in graph._graph:
            continue
        neighbors = graph.get_neighbors(node_id)
        concepts = [n["label"] for n in neighbors if n.get("node_type") == "Concept"]
        methods = [n["label"] for n in neighbors if n.get("node_type") == "Method"]
        if concepts or methods:
            paper_node = graph.get_node(node_id)
            title = paper_node.get("title", arxiv_id)
            lines.append(f"• {title[:60]}:")
            if concepts:
                lines.append(f"  Concepts: {', '.join(concepts[:5])}")
            if methods:
                lines.append(f"  Methods: {', '.join(methods[:3])}")
    return "\n".join(lines) if lines else "Graph context not yet populated."


_HOST_ALIASES: dict[str, str] = {"alex": "A", "jordan": "B", "host a": "A", "host b": "B"}


def _normalize_host(host: str) -> str:
    """Map full character names back to 'A' or 'B' identifiers."""
    return _HOST_ALIASES.get(host.lower().strip(), host)


def _parse_turns(raw: str) -> list[DialogueTurn]:
    """Parse Claude's JSON array response into DialogueTurn objects."""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    def _turn(t: dict) -> DialogueTurn:
        return DialogueTurn(
            host=_normalize_host(t["host"]),
            text=t["text"],
            paper_refs=t.get("paper_refs") or [],
        )

    try:
        turns_data = json.loads(raw)
        return [_turn(t) for t in turns_data]
    except (json.JSONDecodeError, KeyError) as exc:
        logger.error("Script parse error: %s — attempting line-by-line fallback", exc)
        turns = []
        for line in raw.splitlines():
            line = line.strip().rstrip(",")
            if not line or not line.startswith("{"):
                continue
            try:
                obj = json.loads(line)
                turns.append(_turn(obj))
            except Exception:
                continue
        return turns


async def run(
    papers: list[Paper],
    bibliography_path: Path,
    graph: KnowledgeGraph,
    query: QueryParameters,
    episode_id: str,
) -> tuple[PodcastScript, TokenUsage]:
    """Generate a two-host podcast script and save to disk."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    level = _get_expertise_level(query)

    bibliography_content = (
        bibliography_path.read_text(encoding="utf-8")
        if bibliography_path.exists()
        else "Bibliography not available."
    )

    graph_context = _build_graph_context(graph, [p.arxiv_id for p in papers])
    papers_summary = _summarize_papers(papers)
    expertise_description = _EXPERTISE_DESCRIPTIONS[level]

    prompt = _SCRIPT_PROMPT.format(
        topic=query.topic,
        disciplines=", ".join(query.disciplines),
        focus_mode=query.focus_mode,
        expertise_description=expertise_description,
        papers_summary=papers_summary,
        graph_context=graph_context,
        bibliography_content=bibliography_content[:3000],  # Trim to avoid token overflow
        n_papers=len(papers),
    )

    logger.info("ScriptAgent: generating script for %d papers", len(papers))
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    usage = TokenUsage(response.usage.input_tokens, response.usage.output_tokens)

    turns = _parse_turns(response.content[0].text)
    if not turns:
        raise RuntimeError("ScriptAgent: received empty or unparseable script from Claude")

    if COMMERCIAL_MODE:
        turns = [DialogueTurn(host="A", text=_DISCLAIMER_TEXT)] + turns
        logger.info("ScriptAgent: disclaimer turn prepended (commercial mode)")

    title = f"{query.topic.title()} — PapersPod"
    script = PodcastScript(
        episode_id=episode_id,
        title=title,
        turns=turns,
        paper_ids=[p.arxiv_id for p in papers],
    )

    # Save structured JSON
    json_path = DATA_DIR / "scripts" / f"{episode_id}.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w") as f:
        json.dump(script.model_dump(mode="json"), f, indent=2, default=str)

    # Save human-readable Markdown
    md_path = DATA_DIR / "scripts" / f"{episode_id}.md"
    md_lines = [f"# {title}", ""]
    if COMMERCIAL_MODE:
        md_lines += [f"> {_DISCLAIMER_TEXT}", ""]
    for turn in turns:
        host_name = "Alex" if turn.host == "A" else "Jordan"
        md_lines.append(f"**{host_name}:** {turn.text}")
        md_lines.append("")
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    logger.info("ScriptAgent: script has %d turns, saved to %s", len(turns), json_path)
    return script, usage
