import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from core.knowledge_graph import KnowledgeGraph, _normalize_concept
from core.models import Paper, PaperRating


def _make_paper(arxiv_id: str = "2301.12345", title: str = "Test Paper") -> Paper:
    return Paper(
        arxiv_id=arxiv_id,
        title=title,
        authors=["Author A", "Author B"],
        abstract="This paper studies attention mechanisms.",
        published_date=date(2023, 6, 15),
        citation_count=100,
        citation_velocity=50.0,
        s2_tldr="A summary.",
    )


@pytest.fixture
def kg(tmp_path: Path) -> KnowledgeGraph:
    """Fresh KnowledgeGraph using a temp directory."""
    graph_path = tmp_path / "graphs" / "graph.graphml"
    g = KnowledgeGraph(graph_path=graph_path)
    # Override snapshot path to also use tmp_path
    g._snapshot_path = tmp_path / "graphs" / "graph_snapshot.json"
    return g


# --- _normalize_concept ---

def test_normalize_concept_lowercase():
    assert _normalize_concept("Attention Mechanism") == "attention_mechanism"

def test_normalize_concept_strips_whitespace():
    assert _normalize_concept("  transformer  ") == "transformer"

def test_normalize_concept_spaces_to_underscores():
    assert _normalize_concept("multi head attention") == "multi_head_attention"


# --- add_paper ---

def test_add_paper_creates_node(kg: KnowledgeGraph):
    paper = _make_paper()
    node_id = kg.add_paper(paper)
    assert node_id == "paper:2301.12345"
    node = kg.get_node(node_id)
    assert node["title"] == "Test Paper"
    assert node["node_type"] == "Paper"
    assert node["arxiv_id"] == "2301.12345"


def test_add_paper_sets_first_seen_date(kg: KnowledgeGraph):
    paper = _make_paper()
    node_id = kg.add_paper(paper)
    node = kg.get_node(node_id)
    assert node["first_seen_date"] == date.today().isoformat()


def test_add_paper_idempotent(kg: KnowledgeGraph):
    """Adding same paper twice does not create duplicates."""
    paper = _make_paper()
    kg.add_paper(paper)
    kg.add_paper(paper)
    assert kg._graph.number_of_nodes() == 1


def test_add_paper_preserves_first_seen_date(kg: KnowledgeGraph):
    """first_seen_date is set on creation and NOT overwritten on subsequent add."""
    paper = _make_paper()
    node_id = kg.add_paper(paper)
    original_fsd = kg.get_node(node_id)["first_seen_date"]

    # Simulate a later add
    kg.add_paper(paper)
    assert kg.get_node(node_id)["first_seen_date"] == original_fsd


def test_add_paper_stores_citation_data(kg: KnowledgeGraph):
    paper = _make_paper()
    node_id = kg.add_paper(paper)
    node = kg.get_node(node_id)
    assert node["citation_count"] == 100
    assert node["citation_velocity"] == 50.0
    assert node["s2_tldr"] == "A summary."


# --- add_concept ---

def test_add_concept_normalizes_name(kg: KnowledgeGraph):
    node_id = kg.add_concept("Attention Mechanism", description="Core transformer component")
    assert node_id == "concept:attention_mechanism"
    node = kg.get_node(node_id)
    assert node["node_type"] == "Concept"
    assert node["normalized_name"] == "attention_mechanism"


def test_add_concept_idempotent(kg: KnowledgeGraph):
    kg.add_concept("transformers")
    kg.add_concept("transformers")
    assert kg._graph.number_of_nodes() == 1


# --- add_method / add_dataset / add_author ---

def test_add_method(kg: KnowledgeGraph):
    node_id = kg.add_method("Self-Attention")
    assert node_id == "method:self-attention"
    assert kg.get_node(node_id)["node_type"] == "Method"


def test_add_dataset(kg: KnowledgeGraph):
    node_id = kg.add_dataset("ImageNet")
    assert node_id == "dataset:imagenet"
    assert kg.get_node(node_id)["node_type"] == "Dataset"


def test_add_author(kg: KnowledgeGraph):
    node_id = kg.add_author("Ashish Vaswani")
    assert node_id == "author:ashish vaswani"
    assert kg.get_node(node_id)["node_type"] == "Author"


# --- add_edge ---

def test_add_edge(kg: KnowledgeGraph):
    paper_id = kg.add_paper(_make_paper())
    concept_id = kg.add_concept("attention")
    kg.add_edge(paper_id, concept_id, edge_type="STUDIES_CONCEPT")

    assert kg._graph.has_edge(paper_id, concept_id)
    edge_data = kg._graph.edges[paper_id, concept_id]
    assert edge_data["edge_type"] == "STUDIES_CONCEPT"


# --- get_neighbors ---

def test_get_neighbors(kg: KnowledgeGraph):
    paper_id = kg.add_paper(_make_paper())
    concept_id = kg.add_concept("attention")
    kg.add_edge(paper_id, concept_id, edge_type="STUDIES_CONCEPT")

    neighbors = kg.get_neighbors(paper_id)
    neighbor_ids = [n["id"] for n in neighbors]
    assert concept_id in neighbor_ids


# --- search ---

def test_search_by_title(kg: KnowledgeGraph):
    kg.add_paper(_make_paper(title="Attention Is All You Need"))
    results = kg.search("attention")
    assert len(results) == 1
    assert results[0]["title"] == "Attention Is All You Need"


def test_search_no_match(kg: KnowledgeGraph):
    kg.add_paper(_make_paper())
    results = kg.search("completely unrelated xyz")
    assert results == []


# --- update_paper_rating ---

def test_update_paper_rating(kg: KnowledgeGraph):
    paper = _make_paper()
    node_id = kg.add_paper(paper)
    rating = PaperRating(
        paper_id=paper.arxiv_id,
        episode_id="ep1",
        interest_score=5,
        depth_score=4,
        flag_for_reading=True,
        notes="Must read.",
    )
    kg.update_paper_rating(paper.arxiv_id, rating)
    node = kg.get_node(node_id)
    assert node["interest_score"] == 5
    assert node["depth_score"] == 4
    assert node["flagged_for_reading"] is True
    assert node["notes"] == "Must read."


def test_update_paper_rating_missing_paper(kg: KnowledgeGraph):
    """Updating rating for non-existent paper logs warning and does not raise."""
    rating = PaperRating(paper_id="nonexistent", episode_id="ep1", interest_score=3, depth_score=3)
    kg.update_paper_rating("nonexistent", rating)  # Should not raise


# --- get_delta_papers ---

def test_get_delta_papers_returns_new(kg: KnowledgeGraph):
    kg.add_paper(_make_paper())
    today = date.today()
    delta = kg.get_delta_papers(since=today)
    assert len(delta) == 1
    assert delta[0]["arxiv_id"] == "2301.12345"


def test_get_delta_papers_excludes_old(kg: KnowledgeGraph):
    """Papers older than 'since' date are excluded."""
    kg.add_paper(_make_paper())
    # Request delta from tomorrow — no papers qualify
    tomorrow = date.today() + timedelta(days=1)
    delta = kg.get_delta_papers(since=tomorrow)
    assert delta == []


def test_get_delta_papers_only_paper_nodes(kg: KnowledgeGraph):
    """Only Paper nodes are returned, not Concepts."""
    kg.add_paper(_make_paper())
    kg.add_concept("transformers")
    delta = kg.get_delta_papers(since=date.today())
    assert all(d.get("node_type") == "Paper" for d in delta)


# --- to_d3_json ---

def test_to_d3_json_structure(kg: KnowledgeGraph):
    paper_id = kg.add_paper(_make_paper())
    concept_id = kg.add_concept("attention")
    kg.add_edge(paper_id, concept_id, edge_type="STUDIES_CONCEPT")

    d3 = kg.to_d3_json()
    assert "nodes" in d3
    assert "links" in d3
    node_ids = [n["id"] for n in d3["nodes"]]
    assert paper_id in node_ids
    assert concept_id in node_ids
    assert len(d3["links"]) == 1
    assert d3["links"][0]["edge_type"] == "STUDIES_CONCEPT"


# --- save and reload ---

def test_save_and_reload(tmp_path: Path):
    """Graph persists across KnowledgeGraph instances."""
    graph_path = tmp_path / "graphs" / "graph.graphml"
    snapshot_path = tmp_path / "graphs" / "graph_snapshot.json"

    g1 = KnowledgeGraph(graph_path=graph_path)
    g1._snapshot_path = snapshot_path
    g1.add_paper(_make_paper())
    g1.add_concept("attention", description="Core mechanism")

    # Load fresh instance from same file
    g2 = KnowledgeGraph(graph_path=graph_path)
    g2._snapshot_path = snapshot_path
    assert g2._graph.number_of_nodes() == 2
    node = g2.get_node("paper:2301.12345")
    assert node["title"] == "Test Paper"
    assert node["first_seen_date"] == date.today().isoformat()

    # Verify JSON snapshot was written
    assert snapshot_path.exists()
    with open(snapshot_path) as f:
        snapshot = json.load(f)
    assert "nodes" in snapshot
    assert "links" in snapshot
