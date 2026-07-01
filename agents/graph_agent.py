import json
import logging

from core.knowledge_graph import KnowledgeGraph
from core.llm import chat as llm_chat
from core.models import Paper, TokenUsage

logger = logging.getLogger(__name__)

MAX_AUTHORS_PER_PAPER = 25

_EXTRACT_PROMPT = """\
Extract structured knowledge from this research paper abstract.

Return a JSON object with these fields:
{{
  "concepts": [{{"name": "string", "description": "string"}}],
  "methods": [{{"name": "string"}}],
  "datasets": [{{"name": "string", "temporal_scope": "string or null"}}],
  "cites": [{{"title_fragment": "string"}}],
  "concept_relationships": [{{"from": "string", "to": "string", "relationship": "string"}}]
}}

Abstract: {abstract}
Keep names concise (2–5 words). Only extract what is clearly stated.
Return only the JSON object, no other text.\
"""


def _safe_parse_json(text: str) -> dict:
    """Parse JSON from Claude response, stripping markdown fences if present."""
    text = text.strip()
    if text.startswith("```"):
        # Strip ```json ... ``` fences
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("JSON parse error: %s — raw: %s", exc, text[:200])
        return {}


async def run(papers: list[Paper], episode_id: str, graph: KnowledgeGraph) -> tuple[KnowledgeGraph, TokenUsage]:
    """Extract entities/relationships from papers and update the knowledge graph."""
    usage = TokenUsage()

    for paper in papers:
        logger.info("GraphAgent: processing paper %s", paper.arxiv_id)

        # Add paper node
        paper_node_id = graph.add_paper(paper)

        # Add author nodes and edges (capped to avoid O(N) saves on large-collaboration papers)
        authors_to_index = paper.authors[:MAX_AUTHORS_PER_PAPER]
        if len(paper.authors) > MAX_AUTHORS_PER_PAPER:
            logger.warning(
                "GraphAgent: paper %s has %d authors — indexing first %d only",
                paper.arxiv_id, len(paper.authors), MAX_AUTHORS_PER_PAPER,
            )
        for author_name in authors_to_index:
            author_id = graph.add_author(author_name)
            graph.add_edge(paper_node_id, author_id, edge_type="CO_AUTHORED_BY")

        # Extract entities via LLM
        result = llm_chat(
            messages=[{
                "role": "user",
                "content": _EXTRACT_PROMPT.format(abstract=paper.abstract),
            }],
            max_tokens=1024,
            stage="graph",
        )
        usage += TokenUsage(result.input_tokens, result.output_tokens)
        data = _safe_parse_json(result.text)

        # Add concepts
        for concept in data.get("concepts", []):
            name = concept.get("name", "")
            if not name:
                continue
            concept_id = graph.add_concept(name, description=concept.get("description", ""))
            graph.add_edge(paper_node_id, concept_id, edge_type="STUDIES_CONCEPT")

        # Add methods
        for method in data.get("methods", []):
            name = method.get("name", "")
            if not name:
                continue
            method_id = graph.add_method(name)
            graph.add_edge(paper_node_id, method_id, edge_type="USES_METHOD")

        # Add datasets
        for dataset in data.get("datasets", []):
            name = dataset.get("name", "")
            if not name:
                continue
            temporal = dataset.get("temporal_scope")
            dataset_id = graph.add_dataset(name, temporal_scope=temporal)
            graph.add_edge(paper_node_id, dataset_id, edge_type="APPLIED_TO_DATASET")

        # Add concept-to-concept relationships
        for rel in data.get("concept_relationships", []):
            from_name = rel.get("from", "")
            to_name = rel.get("to", "")
            relationship = rel.get("relationship", "RELATED_TO")
            if not from_name or not to_name:
                continue
            from_id = graph.add_concept(from_name)
            to_id = graph.add_concept(to_name)
            graph.add_edge(from_id, to_id, edge_type="RELATED_TO", relationship=relationship)

        graph.save()
        logger.info(
            "GraphAgent: added paper %s — %d concepts, %d methods, %d datasets",
            paper.arxiv_id,
            len(data.get("concepts", [])),
            len(data.get("methods", [])),
            len(data.get("datasets", [])),
        )

    logger.info("GraphAgent: graph has %d nodes", graph._graph.number_of_nodes())
    return graph, usage
