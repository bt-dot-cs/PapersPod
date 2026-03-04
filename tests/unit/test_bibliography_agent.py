from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.models import ExpertiseLevel, ExpertiseProfile, Paper, QueryParameters, UserProfile


def _make_paper(arxiv_id: str = "2301.12345", title: str = "Test Paper") -> Paper:
    return Paper(
        arxiv_id=arxiv_id,
        title=title,
        authors=["Author A"],
        abstract="This paper proposes a novel approach.",
        published_date=date(2023, 6, 15),
        citation_count=100,
        s2_tldr="A one-sentence summary.",
    )


def _make_query(expertise_level: ExpertiseLevel = ExpertiseLevel.intermediate) -> QueryParameters:
    return QueryParameters(
        topic="attention mechanisms",
        disciplines=["machine learning"],
        publication_date_range=(date(2022, 1, 1), date(2026, 1, 1)),
        user_profile=UserProfile(
            expertise=[ExpertiseProfile(discipline="machine learning", level=expertise_level)],
            default_level=ExpertiseLevel.intermediate,
        ),
    )


def _make_mock_anthropic(annotation_text: str = "APA Citation.\n\nAnnotation text here."):
    """Build a mock Anthropic client that returns canned responses."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=annotation_text)]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    return mock_client


@pytest.mark.asyncio
async def test_bibliography_returns_path(tmp_path: Path):
    """run() returns a Path object."""
    papers = [_make_paper()]
    query = _make_query()

    with patch("agents.bibliography_agent.anthropic.Anthropic") as MockAnthropic, \
         patch("agents.bibliography_agent.DATA_DIR", tmp_path):
        MockAnthropic.return_value = _make_mock_anthropic()
        from agents.bibliography_agent import run
        result = await run(papers, query, episode_id="ep1")

    assert isinstance(result, Path)


@pytest.mark.asyncio
async def test_bibliography_file_exists(tmp_path: Path):
    """Output file exists and contains content."""
    papers = [_make_paper()]
    query = _make_query()

    with patch("agents.bibliography_agent.anthropic.Anthropic") as MockAnthropic, \
         patch("agents.bibliography_agent.DATA_DIR", tmp_path):
        MockAnthropic.return_value = _make_mock_anthropic("Full Citation.\n\nAnnotation.")
        from agents.bibliography_agent import run
        result = await run(papers, query, episode_id="ep1")

    assert result.exists()
    content = result.read_text()
    assert len(content) > 0


@pytest.mark.asyncio
async def test_bibliography_contains_all_papers(tmp_path: Path):
    """All papers are included in the output."""
    papers = [
        _make_paper("2301.00001", "Paper One"),
        _make_paper("2301.00002", "Paper Two"),
    ]
    query = _make_query()

    call_count = 0

    def annotation_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock = MagicMock()
        mock.content = [MagicMock(text=f"Annotation for call {call_count}.")]
        return mock

    with patch("agents.bibliography_agent.anthropic.Anthropic") as MockAnthropic, \
         patch("agents.bibliography_agent.DATA_DIR", tmp_path):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = annotation_side_effect
        MockAnthropic.return_value = mock_client
        from agents.bibliography_agent import run
        result = await run(papers, query, episode_id="ep1")

    # 2 papers + 1 intro = 3 total calls
    assert mock_client.messages.create.call_count == 3


@pytest.mark.asyncio
async def test_bibliography_expertise_level_in_prompt(tmp_path: Path):
    """The expertise level is included in the prompt sent to Claude."""
    papers = [_make_paper()]
    query = _make_query(expertise_level=ExpertiseLevel.expert)

    captured_prompts = []

    def capture_prompt(*args, **kwargs):
        messages = kwargs.get("messages", [])
        if messages:
            captured_prompts.append(messages[0]["content"])
        mock = MagicMock()
        mock.content = [MagicMock(text="Expert annotation.")]
        return mock

    with patch("agents.bibliography_agent.anthropic.Anthropic") as MockAnthropic, \
         patch("agents.bibliography_agent.DATA_DIR", tmp_path):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = capture_prompt
        MockAnthropic.return_value = mock_client
        from agents.bibliography_agent import run
        await run(papers, query, episode_id="ep1")

    # First call is the annotation prompt — should contain "expert"
    assert captured_prompts, "No prompts captured"
    assert "expert" in captured_prompts[0].lower()


@pytest.mark.asyncio
async def test_bibliography_saved_to_correct_path(tmp_path: Path):
    """File is saved to data/bibliographies/{episode_id}.md."""
    papers = [_make_paper()]
    query = _make_query()

    with patch("agents.bibliography_agent.anthropic.Anthropic") as MockAnthropic, \
         patch("agents.bibliography_agent.DATA_DIR", tmp_path):
        MockAnthropic.return_value = _make_mock_anthropic()
        from agents.bibliography_agent import run
        result = await run(papers, query, episode_id="test-episode-123")

    assert result == tmp_path / "bibliographies" / "test-episode-123.md"
