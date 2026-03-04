from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.semantic_scholar_client import enrich_papers, _compute_citation_velocity
from core.models import Paper


def _make_paper(
    arxiv_id: str = "2301.12345",
    published_date: date = date(2023, 1, 15),
) -> Paper:
    return Paper(
        arxiv_id=arxiv_id,
        title="Test Paper",
        authors=["Author A"],
        abstract="Test abstract",
        published_date=published_date,
    )


def _make_s2_result(
    citation_count: int = 100,
    tldr_text: str | None = "One sentence summary.",
) -> MagicMock:
    result = MagicMock()
    result.citationCount = citation_count
    if tldr_text:
        result.tldr = {"text": tldr_text}
    else:
        result.tldr = None
    return result


# --- _compute_citation_velocity ---

def test_citation_velocity_recent_paper():
    # Published about 1 year ago → velocity ≈ citation_count
    published = date(2025, 3, 4)
    velocity = _compute_citation_velocity(365, published)
    assert velocity > 0


def test_citation_velocity_minimum_denominator():
    # Very new paper → denominator floored to 1 year
    published = date.today()
    velocity = _compute_citation_velocity(50, published)
    assert velocity == 50.0


def test_citation_velocity_old_paper():
    # Published ~10 years ago → velocity = citations / ~10
    published = date(2016, 3, 4)
    velocity = _compute_citation_velocity(1000, published)
    assert 90 < velocity < 120  # roughly 1000 / 10


# --- enrich_papers ---

@pytest.mark.asyncio
async def test_enrich_papers_success():
    """Successful enrichment sets citation_count, citation_velocity, s2_tldr."""
    paper = _make_paper()
    s2_result = _make_s2_result(citation_count=200, tldr_text="Great paper.")

    with patch("core.semantic_scholar_client.SemanticScholar") as MockS2, \
         patch("core.semantic_scholar_client.asyncio.sleep", new_callable=AsyncMock):
        MockS2.return_value.get_paper.return_value = s2_result
        result = await enrich_papers([paper])

    assert len(result) == 1
    assert result[0].citation_count == 200
    assert result[0].citation_velocity > 0
    assert result[0].s2_tldr == "Great paper."


@pytest.mark.asyncio
async def test_enrich_papers_not_found():
    """Paper not in S2 returns unchanged with a warning."""
    paper = _make_paper()

    with patch("core.semantic_scholar_client.SemanticScholar") as MockS2, \
         patch("core.semantic_scholar_client.asyncio.sleep", new_callable=AsyncMock):
        MockS2.return_value.get_paper.return_value = None
        result = await enrich_papers([paper])

    assert len(result) == 1
    assert result[0].citation_count is None
    assert result[0].s2_tldr is None


@pytest.mark.asyncio
async def test_enrich_papers_no_tldr():
    """Paper with no TLDR leaves s2_tldr as None."""
    paper = _make_paper()
    s2_result = _make_s2_result(citation_count=50, tldr_text=None)

    with patch("core.semantic_scholar_client.SemanticScholar") as MockS2, \
         patch("core.semantic_scholar_client.asyncio.sleep", new_callable=AsyncMock):
        MockS2.return_value.get_paper.return_value = s2_result
        result = await enrich_papers([paper])

    assert result[0].s2_tldr is None
    assert result[0].citation_count == 50


@pytest.mark.asyncio
async def test_enrich_papers_rate_limit_applied():
    """asyncio.sleep is called once per paper."""
    papers = [_make_paper(arxiv_id=f"2301.0000{i}") for i in range(3)]
    s2_result = _make_s2_result()

    with patch("core.semantic_scholar_client.SemanticScholar") as MockS2, \
         patch("core.semantic_scholar_client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        MockS2.return_value.get_paper.return_value = s2_result
        await enrich_papers(papers)

    assert mock_sleep.call_count == 3


@pytest.mark.asyncio
async def test_enrich_papers_exception_handled():
    """S2 exception logs warning and returns paper unchanged."""
    paper = _make_paper()

    with patch("core.semantic_scholar_client.SemanticScholar") as MockS2, \
         patch("core.semantic_scholar_client.asyncio.sleep", new_callable=AsyncMock):
        MockS2.return_value.get_paper.side_effect = Exception("Connection error")
        result = await enrich_papers([paper])

    assert len(result) == 1
    assert result[0].citation_count is None


@pytest.mark.asyncio
async def test_enrich_papers_citation_velocity_calculation():
    """citation_velocity is correctly derived from citation_count and published_date."""
    published = date(2024, 3, 4)
    citation_count = 100
    paper = _make_paper(published_date=published)
    s2_result = _make_s2_result(citation_count=citation_count)

    with patch("core.semantic_scholar_client.SemanticScholar") as MockS2, \
         patch("core.semantic_scholar_client.asyncio.sleep", new_callable=AsyncMock):
        MockS2.return_value.get_paper.return_value = s2_result
        result = await enrich_papers([paper])

    # Compute expected velocity the same way the implementation does
    from core.semantic_scholar_client import _compute_citation_velocity
    expected = _compute_citation_velocity(citation_count, published)
    assert result[0].citation_velocity == expected
