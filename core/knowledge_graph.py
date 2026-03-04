import json
import logging
from datetime import date
from pathlib import Path
from typing import Optional

import networkx as nx

from core.config import GRAPH_PATH, GRAPH_SNAPSHOT_PATH
from core.models import Paper, PaperRating

logger = logging.getLogger(__name__)


def _normalize_concept(name: str) -> str:
    """Lowercase, strip, replace spaces with underscores."""
    return name.lower().strip().replace(" ", "_")


class KnowledgeGraph:
    def __init__(self, graph_path: Optional[Path] = None) -> None:
        self._graph_path = graph_path if graph_path is not None else GRAPH_PATH
        self._snapshot_path = GRAPH_SNAPSHOT_PATH
        if self._graph_path.exists():
            self._graph: nx.DiGraph = nx.read_graphml(self._graph_path)
            logger.info("Loaded graph from %s (%d nodes)", self._graph_path, self._graph.number_of_nodes())
        else:
            self._graph = nx.DiGraph()
            logger.info("Created new empty graph")

    # ------------------------------------------------------------------
    # Add nodes
    # ------------------------------------------------------------------

    def add_paper(self, paper: Paper) -> str:
        """Add or update a Paper node. Returns node_id. Sets first_seen_date on creation only."""
        node_id = f"paper:{paper.arxiv_id}"
        today = date.today().isoformat()

        if node_id not in self._graph:
            self._graph.add_node(
                node_id,
                node_type="Paper",
                label=paper.title,
                arxiv_id=paper.arxiv_id,
                title=paper.title,
                authors=json.dumps(paper.authors),
                abstract=paper.abstract,
                published_date=paper.published_date.isoformat(),
                first_seen_date=today,
            )
        else:
            # Update mutable fields; do NOT overwrite first_seen_date
            self._graph.nodes[node_id].update(
                title=paper.title,
                authors=json.dumps(paper.authors),
                abstract=paper.abstract,
            )

        # Always update enrichment fields if present
        if paper.citation_count is not None:
            self._graph.nodes[node_id]["citation_count"] = paper.citation_count
        if paper.citation_velocity is not None:
            self._graph.nodes[node_id]["citation_velocity"] = paper.citation_velocity
        if paper.s2_tldr is not None:
            self._graph.nodes[node_id]["s2_tldr"] = paper.s2_tldr
        if paper.study_period_start is not None:
            self._graph.nodes[node_id]["study_period_start"] = paper.study_period_start.isoformat()
        if paper.study_period_end is not None:
            self._graph.nodes[node_id]["study_period_end"] = paper.study_period_end.isoformat()

        self.save()
        return node_id

    def add_concept(self, name: str, description: str = "") -> str:
        """Add or update a Concept node. Returns node_id."""
        normalized = _normalize_concept(name)
        node_id = f"concept:{normalized}"
        today = date.today().isoformat()

        if node_id not in self._graph:
            self._graph.add_node(
                node_id,
                node_type="Concept",
                label=name,
                normalized_name=normalized,
                description=description,
                first_seen_date=today,
            )
        else:
            if description:
                self._graph.nodes[node_id]["description"] = description

        self.save()
        return node_id

    def add_method(self, name: str) -> str:
        """Add or update a Method node. Returns node_id."""
        node_id = f"method:{_normalize_concept(name)}"
        today = date.today().isoformat()

        if node_id not in self._graph:
            self._graph.add_node(
                node_id,
                node_type="Method",
                label=name,
                first_seen_date=today,
            )

        self.save()
        return node_id

    def add_dataset(self, name: str, temporal_scope: Optional[tuple] = None) -> str:
        """Add or update a Dataset node. Returns node_id."""
        node_id = f"dataset:{_normalize_concept(name)}"
        today = date.today().isoformat()

        if node_id not in self._graph:
            attrs: dict = {"node_type": "Dataset", "label": name, "first_seen_date": today}
            if temporal_scope:
                attrs["temporal_scope"] = str(temporal_scope)
            self._graph.add_node(node_id, **attrs)

        self.save()
        return node_id

    def add_author(self, name: str) -> str:
        """Add or update an Author node. Returns node_id."""
        node_id = f"author:{name.lower().strip()}"
        today = date.today().isoformat()

        if node_id not in self._graph:
            self._graph.add_node(
                node_id,
                node_type="Author",
                label=name,
                first_seen_date=today,
            )

        self.save()
        return node_id

    # ------------------------------------------------------------------
    # Add edges
    # ------------------------------------------------------------------

    def add_edge(self, source_id: str, target_id: str, edge_type: str, **attrs) -> None:
        """Add a directed edge between two nodes."""
        self._graph.add_edge(source_id, target_id, edge_type=edge_type, **attrs)
        self.save()

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_node(self, node_id: str) -> dict:
        """Return node attributes dict, or empty dict if not found."""
        if node_id not in self._graph:
            return {}
        return dict(self._graph.nodes[node_id])

    def get_neighbors(self, node_id: str) -> list[dict]:
        """Return list of neighbor node dicts (successors + predecessors)."""
        neighbors = []
        for nid in set(self._graph.successors(node_id)) | set(self._graph.predecessors(node_id)):
            attrs = dict(self._graph.nodes[nid])
            attrs["id"] = nid
            neighbors.append(attrs)
        return neighbors

    def search(self, query: str) -> list[dict]:
        """Substring match on label, title, normalized_name, or description."""
        q = query.lower()
        results = []
        for nid, attrs in self._graph.nodes(data=True):
            searchable = " ".join(
                str(attrs.get(field, ""))
                for field in ("label", "title", "normalized_name", "description", "abstract")
            ).lower()
            if q in searchable:
                result = dict(attrs)
                result["id"] = nid
                results.append(result)
        return results

    def update_paper_rating(self, arxiv_id: str, rating: PaperRating) -> None:
        """Store user rating attributes on a Paper node."""
        node_id = f"paper:{arxiv_id}"
        if node_id not in self._graph:
            logger.warning("update_paper_rating: paper not found — %s", arxiv_id)
            return
        self._graph.nodes[node_id].update(
            interest_score=rating.interest_score,
            depth_score=rating.depth_score,
            flagged_for_reading=rating.flag_for_reading,
        )
        if rating.notes:
            self._graph.nodes[node_id]["notes"] = rating.notes
        self.save()

    def get_delta_papers(self, since: date) -> list[dict]:
        """Return Paper nodes whose first_seen_date >= since."""
        results = []
        for nid, attrs in self._graph.nodes(data=True):
            if attrs.get("node_type") != "Paper":
                continue
            fsd = attrs.get("first_seen_date")
            if fsd and date.fromisoformat(fsd) >= since:
                result = dict(attrs)
                result["id"] = nid
                results.append(result)
        return results

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_d3_json(self) -> dict:
        """Return D3-compatible {nodes, links} dict."""
        nodes = [
            {"id": nid, **attrs}
            for nid, attrs in self._graph.nodes(data=True)
        ]
        links = [
            {"source": u, "target": v, **data}
            for u, v, data in self._graph.edges(data=True)
        ]
        return {"nodes": nodes, "links": links}

    def save(self) -> None:
        """Persist to GraphML and JSON snapshot."""
        self._graph_path.parent.mkdir(parents=True, exist_ok=True)
        nx.write_graphml(self._graph, self._graph_path)

        self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._snapshot_path, "w") as f:
            json.dump(self.to_d3_json(), f, indent=2)
