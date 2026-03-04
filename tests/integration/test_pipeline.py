"""
Integration test: full pipeline with all external APIs mocked.

Verifies end-to-end flow without real network calls:
  arXiv → Semantic Scholar → Claude (bib + graph + script) → ElevenLabs → pydub
"""

import io
import json
import math
import struct
from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydub import AudioSegment

from core.models import QueryParameters


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_fixture_papers() -> list[dict]:
    fixture = Path(__file__).parent.parent / "fixtures" / "sample_papers.json"
    return json.loads(fixture.read_text())


def _make_mp3_bytes(duration_ms: int = 200) -> bytes:
    sample_rate = 44100
    n = int(sample_rate * duration_ms / 1000)
    raw = b"".join(
        struct.pack("<h", int(16383 * math.sin(2 * math.pi * 440 * i / sample_rate)))
        for i in range(n)
    )
    seg = AudioSegment(data=raw, sample_width=2, frame_rate=sample_rate, channels=1)
    buf = io.BytesIO()
    seg.export(buf, format="mp3", bitrate="128k")
    return buf.getvalue()


def _make_arxiv_result(paper_dict: dict) -> MagicMock:
    from datetime import timezone
    result = MagicMock()
    result.entry_id = f"https://arxiv.org/abs/{paper_dict['arxiv_id']}"
    result.title = paper_dict["title"]
    result.authors = [MagicMock(__str__=lambda self, a=a: a) for a in paper_dict["authors"]]
    result.summary = paper_dict["abstract"]
    result.published = datetime.fromisoformat(paper_dict["published_date"]).replace(
        tzinfo=timezone.utc
    )
    result.journal_ref = "Published"
    result.pdf_url = paper_dict.get("pdf_url", "")
    return result


def _make_s2_result(paper_dict: dict) -> MagicMock:
    result = MagicMock()
    result.citationCount = paper_dict.get("citation_count", 100)
    result.tldr = {"text": paper_dict.get("s2_tldr", "A summary.")}
    return result


def _make_claude_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    return resp


def _make_script_json() -> str:
    turns = [
        {"host": "A", "text": "Welcome to PapersPod. Today we explore attention mechanisms."},
        {"host": "B", "text": "What makes the Transformer architecture so significant?"},
        {"host": "A", "text": "The key insight is self-attention — every token attends to every other."},
        {"host": "B", "text": "And BERT took that further with bidirectional pre-training."},
        {"host": "A", "text": "Exactly. Though interestingly, GPT-3 contradicts the need for fine-tuning."},
        {"host": "B", "text": "So where does that leave us? What questions remain open?"},
    ]
    return json.dumps(turns)


def _make_graph_extract_json() -> str:
    return json.dumps({
        "concepts": [{"name": "attention mechanism", "description": "Core transformer component"}],
        "methods": [{"name": "self-attention"}],
        "datasets": [],
        "cites": [],
        "concept_relationships": [],
    })


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_pipeline_mocked(tmp_path: Path):
    """
    Full pipeline run with all external APIs mocked.
    Asserts that all output files are created and have correct structure.
    """
    fixture_papers = _load_fixture_papers()
    arxiv_results = [_make_arxiv_result(p) for p in fixture_papers]
    s2_results = {p["arxiv_id"]: _make_s2_result(p) for p in fixture_papers}
    mp3_bytes = _make_mp3_bytes()

    query = QueryParameters(
        topic="transformer architectures",
        disciplines=["machine learning"],
        publication_date_range=(date(2017, 1, 1), date(2026, 1, 1)),
        max_papers=3,
    )
    episode_id = "2026-03-04_transformer-architectures_test"

    def s2_get_paper(paper_id, fields=None):
        arxiv_id = paper_id.replace("ARXIV:", "")
        return s2_results.get(arxiv_id)

    def claude_respond(*args, **kwargs):
        messages = kwargs.get("messages", [])
        content = messages[0]["content"] if messages else ""
        if "Extract structured knowledge" in content:
            return _make_claude_response(_make_graph_extract_json())
        elif "annotated bibliography" in content.lower():
            return _make_claude_response("**Vaswani et al. (2017).** Attention Is All You Need.\n\nAnnotation text.")
        elif "introductory paragraph" in content.lower():
            return _make_claude_response("This episode explores transformers.")
        elif "podcast script" in content.lower() or "HOST A" in content or "HOST B" in content:
            return _make_claude_response(_make_script_json())
        return _make_claude_response("Default response.")

    with patch("core.arxiv_client.arxiv.Client") as MockArxiv, \
         patch("core.arxiv_client.asyncio.sleep", new_callable=AsyncMock), \
         patch("core.semantic_scholar_client.SemanticScholar") as MockS2, \
         patch("core.semantic_scholar_client.asyncio.sleep", new_callable=AsyncMock), \
         patch("core.arxiv_client.anthropic.Anthropic"), \
         patch("agents.bibliography_agent.anthropic.Anthropic") as MockBibAnth, \
         patch("agents.graph_agent.anthropic.Anthropic") as MockGraphAnth, \
         patch("agents.script_agent.anthropic.Anthropic") as MockScriptAnth, \
         patch("agents.voice_agent.ElevenLabs") as MockEL, \
         patch("core.config.DATA_DIR", tmp_path), \
         patch("core.knowledge_graph.GRAPH_PATH", tmp_path / "graphs" / "graph.graphml"), \
         patch("core.knowledge_graph.GRAPH_SNAPSHOT_PATH", tmp_path / "graphs" / "graph_snapshot.json"), \
         patch("agents.bibliography_agent.DATA_DIR", tmp_path), \
         patch("agents.fetcher_agent.DATA_DIR", tmp_path), \
         patch("agents.script_agent.DATA_DIR", tmp_path), \
         patch("agents.voice_agent.DATA_DIR", tmp_path), \
         patch("agents.orchestrator.DATA_DIR", tmp_path):

        MockArxiv.return_value.results.return_value = iter(arxiv_results)
        MockS2.return_value.get_paper.side_effect = s2_get_paper

        for mock_ath in (MockBibAnth, MockGraphAnth, MockScriptAnth):
            mock_ath.return_value.messages.create.side_effect = claude_respond

        MockEL.return_value.text_to_speech.convert.side_effect = \
            lambda voice_id, text, model_id: iter([mp3_bytes])

        from agents.orchestrator import run_pipeline
        episode = await run_pipeline(query, episode_id)

    # --- Assertions ---

    # Audio file exists
    audio_path = tmp_path / "audio" / f"{episode_id}.mp3"
    assert audio_path.exists(), f"Audio file missing: {audio_path}"
    assert audio_path.stat().st_size > 0

    # Knowledge graph exists and has >= 3 nodes
    graph_path = tmp_path / "graphs" / "graph.graphml"
    assert graph_path.exists(), "graph.graphml missing"
    import networkx as nx
    g = nx.read_graphml(graph_path)
    assert g.number_of_nodes() >= 3, f"Graph has only {g.number_of_nodes()} nodes"

    # Bibliography exists with content
    bib_path = tmp_path / "bibliographies" / f"{episode_id}.md"
    assert bib_path.exists(), "Bibliography file missing"
    assert len(bib_path.read_text()) > 0

    # Script JSON exists with both A and B hosts
    script_path = tmp_path / "scripts" / f"{episode_id}.json"
    assert script_path.exists(), "Script JSON missing"
    with open(script_path) as f:
        script_data = json.load(f)
    assert "turns" in script_data
    hosts = {t["host"] for t in script_data["turns"]}
    assert "A" in hosts and "B" in hosts

    # Episode record saved
    episode_file = tmp_path / "papers" / f"{episode_id}_episode.json"
    assert episode_file.exists(), "Episode JSON missing"
    with open(episode_file) as f:
        ep_data = json.load(f)
    assert ep_data["episode_id"] == episode_id
    assert len(ep_data["papers"]) == 3

    # Delta tracking: all papers have first_seen_date = today
    from core.knowledge_graph import KnowledgeGraph
    kg = KnowledgeGraph(graph_path=tmp_path / "graphs" / "graph.graphml")
    kg._snapshot_path = tmp_path / "graphs" / "graph_snapshot.json"
    delta = kg.get_delta_papers(since=date.today())
    assert len(delta) >= 3, f"Delta tracking: expected >=3 new papers, got {len(delta)}"
