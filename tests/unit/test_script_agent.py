import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.models import ExpertiseLevel, Paper, QueryParameters


def _make_paper(arxiv_id: str = "2301.12345") -> Paper:
    return Paper(
        arxiv_id=arxiv_id,
        title="Attention Is All You Need",
        authors=["Vaswani, A."],
        abstract="We propose a new simple network architecture, the Transformer.",
        published_date=date(2017, 6, 12),
        citation_count=80000,
        s2_tldr="Introduces the transformer architecture.",
    )


def _make_query() -> QueryParameters:
    return QueryParameters(
        topic="attention mechanisms",
        disciplines=["machine learning"],
        publication_date_range=(date(2022, 1, 1), date(2026, 1, 1)),
    )


def _make_script_json(n_turns: int = 6) -> str:
    turns = []
    for i in range(n_turns):
        host = "A" if i % 2 == 0 else "B"
        turns.append({"host": host, "text": f"Turn {i} dialogue text here."})
    return json.dumps(turns)


def _make_mock_client(script_json: str):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=script_json)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    return mock_client


@pytest.mark.asyncio
async def test_script_returns_podcast_script(tmp_path: Path):
    """run() returns a PodcastScript with turns."""
    from core.knowledge_graph import KnowledgeGraph
    from agents.script_agent import run

    graph_path = tmp_path / "graph.graphml"
    kg = KnowledgeGraph(graph_path=graph_path)
    kg._snapshot_path = tmp_path / "snapshot.json"
    bibliography = tmp_path / "bib.md"
    bibliography.write_text("# Bibliography\n\nTest content.", encoding="utf-8")

    with patch("agents.script_agent.anthropic.Anthropic") as MockAnthropic, \
         patch("agents.script_agent.DATA_DIR", tmp_path):
        MockAnthropic.return_value = _make_mock_client(_make_script_json(6))
        result = await run(
            papers=[_make_paper()],
            bibliography_path=bibliography,
            graph=kg,
            query=_make_query(),
            episode_id="ep1",
        )

    from core.models import PodcastScript
    assert isinstance(result, PodcastScript)
    assert len(result.turns) >= 4


@pytest.mark.asyncio
async def test_script_has_both_hosts(tmp_path: Path):
    """Both host A and host B appear in the turns."""
    from core.knowledge_graph import KnowledgeGraph
    from agents.script_agent import run

    kg = KnowledgeGraph(graph_path=tmp_path / "graph.graphml")
    kg._snapshot_path = tmp_path / "snapshot.json"
    bibliography = tmp_path / "bib.md"
    bibliography.write_text("Bibliography", encoding="utf-8")

    with patch("agents.script_agent.anthropic.Anthropic") as MockAnthropic, \
         patch("agents.script_agent.DATA_DIR", tmp_path):
        MockAnthropic.return_value = _make_mock_client(_make_script_json(6))
        result = await run(
            papers=[_make_paper()],
            bibliography_path=bibliography,
            graph=kg,
            query=_make_query(),
            episode_id="ep1",
        )

    hosts = {turn.host for turn in result.turns}
    assert "A" in hosts
    assert "B" in hosts


@pytest.mark.asyncio
async def test_script_saved_to_json_and_md(tmp_path: Path):
    """Both JSON and Markdown script files are written."""
    from core.knowledge_graph import KnowledgeGraph
    from agents.script_agent import run

    kg = KnowledgeGraph(graph_path=tmp_path / "graph.graphml")
    kg._snapshot_path = tmp_path / "snapshot.json"
    bibliography = tmp_path / "bib.md"
    bibliography.write_text("Bibliography", encoding="utf-8")

    episode_id = "test-episode-abc"
    with patch("agents.script_agent.anthropic.Anthropic") as MockAnthropic, \
         patch("agents.script_agent.DATA_DIR", tmp_path):
        MockAnthropic.return_value = _make_mock_client(_make_script_json(4))
        await run(
            papers=[_make_paper()],
            bibliography_path=bibliography,
            graph=kg,
            query=_make_query(),
            episode_id=episode_id,
        )

    assert (tmp_path / "scripts" / f"{episode_id}.json").exists()
    assert (tmp_path / "scripts" / f"{episode_id}.md").exists()


@pytest.mark.asyncio
async def test_script_json_has_valid_turns(tmp_path: Path):
    """The saved JSON file has a valid 'turns' array."""
    from core.knowledge_graph import KnowledgeGraph
    from agents.script_agent import run

    kg = KnowledgeGraph(graph_path=tmp_path / "graph.graphml")
    kg._snapshot_path = tmp_path / "snapshot.json"
    bibliography = tmp_path / "bib.md"
    bibliography.write_text("Bibliography", encoding="utf-8")

    episode_id = "ep-json-test"
    with patch("agents.script_agent.anthropic.Anthropic") as MockAnthropic, \
         patch("agents.script_agent.DATA_DIR", tmp_path):
        MockAnthropic.return_value = _make_mock_client(_make_script_json(4))
        await run(
            papers=[_make_paper()],
            bibliography_path=bibliography,
            graph=kg,
            query=_make_query(),
            episode_id=episode_id,
        )

    with open(tmp_path / "scripts" / f"{episode_id}.json") as f:
        data = json.load(f)

    assert "turns" in data
    assert len(data["turns"]) == 4
    assert data["turns"][0]["host"] in ("A", "B")
