import asyncio
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.arxiv_client import fetch_papers, build_search_query as _build_search_query
from core.models import QueryParameters


def _make_arxiv_result(
    arxiv_id: str = "2301.12345",
    title: str = "Test Paper",
    authors: list[str] | None = None,
    abstract: str = "This is an abstract.",
    published: datetime | None = None,
    journal_ref: str | None = None,
    pdf_url: str = "https://arxiv.org/pdf/2301.12345",
    doi: str | None = None,
) -> MagicMock:
    """Create a mock arxiv.Result object."""
    result = MagicMock()
    result.entry_id = f"https://arxiv.org/abs/{arxiv_id}"
    result.title = title
    result.authors = [MagicMock(__str__=lambda self: a) for a in (authors or ["Author A"])]
    result.summary = abstract
    result.published = published or datetime(2023, 6, 15, tzinfo=timezone.utc)
    result.journal_ref = journal_ref
    result.pdf_url = pdf_url
    result.doi = doi
    result.links = []
    return result


def _make_query(
    topic: str = "transformers",
    disciplines: list[str] | None = None,
    max_papers: int = 5,
    pub_start: date = date(2022, 1, 1),
    pub_end: date = date(2026, 1, 1),
    include_preprints: bool = True,
    study_data_period: tuple | None = None,
) -> QueryParameters:
    return QueryParameters(
        topic=topic,
        disciplines=["machine learning"] if disciplines is None else disciplines,
        publication_date_range=(pub_start, pub_end),
        max_papers=max_papers,
        include_preprints=include_preprints,
        study_data_period=study_data_period,
    )


# --- _build_search_query ---

def test_build_search_query_with_known_discipline():
    qp = _make_query(topic="attention mechanisms", disciplines=["machine learning"])
    query = _build_search_query(qp)
    assert "attention mechanisms" in query
    assert "cs.LG" in query


def test_build_search_query_unknown_discipline():
    qp = _make_query(topic="quantum computing", disciplines=["unknown field"])
    query = _build_search_query(qp)
    assert "quantum computing" in query
    # Unknown discipline produces no category filter
    assert "cat:" not in query


def test_build_search_query_no_disciplines():
    qp = _make_query(topic="neural networks", disciplines=[])
    query = _build_search_query(qp)
    assert query == "neural networks"


# --- fetch_papers ---

@pytest.mark.asyncio
async def test_fetch_papers_basic():
    """Basic fetch returns a list of Paper objects."""
    result = _make_arxiv_result(published=datetime(2023, 6, 15, tzinfo=timezone.utc))
    qp = _make_query()

    with patch("core.arxiv_client.arxiv.Client") as MockClient, \
         patch("core.arxiv_client.asyncio.sleep", new_callable=AsyncMock):
        MockClient.return_value.results.return_value = iter([result])
        papers = await fetch_papers(qp)

    assert len(papers) == 1
    assert papers[0].arxiv_id == "2301.12345"
    assert papers[0].title == "Test Paper"
    assert papers[0].published_date == date(2023, 6, 15)


@pytest.mark.asyncio
async def test_fetch_papers_date_range_filtering():
    """Papers outside the date range are excluded."""
    in_range = _make_arxiv_result(
        arxiv_id="2301.00001",
        published=datetime(2023, 6, 15, tzinfo=timezone.utc),
    )
    out_of_range = _make_arxiv_result(
        arxiv_id="2301.00002",
        published=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    qp = _make_query(pub_start=date(2022, 1, 1), pub_end=date(2026, 1, 1))

    with patch("core.arxiv_client.arxiv.Client") as MockClient, \
         patch("core.arxiv_client.asyncio.sleep", new_callable=AsyncMock):
        MockClient.return_value.results.return_value = iter([in_range, out_of_range])
        papers = await fetch_papers(qp)

    assert len(papers) == 1
    assert papers[0].arxiv_id == "2301.00001"


@pytest.mark.asyncio
async def test_fetch_papers_exclude_preprints():
    """With include_preprints=False, papers without journal_ref are skipped."""
    preprint = _make_arxiv_result(arxiv_id="2301.00001", journal_ref=None)
    published = _make_arxiv_result(arxiv_id="2301.00002", journal_ref="Nature 2023")
    qp = _make_query(include_preprints=False)

    with patch("core.arxiv_client.arxiv.Client") as MockClient, \
         patch("core.arxiv_client.asyncio.sleep", new_callable=AsyncMock):
        MockClient.return_value.results.return_value = iter([preprint, published])
        papers = await fetch_papers(qp)

    assert len(papers) == 1
    assert papers[0].arxiv_id == "2301.00002"


@pytest.mark.asyncio
async def test_fetch_papers_rate_limit_applied():
    """asyncio.sleep is called between results."""
    results = [
        _make_arxiv_result(arxiv_id=f"2301.0000{i}") for i in range(3)
    ]
    qp = _make_query(max_papers=3)

    with patch("core.arxiv_client.arxiv.Client") as MockClient, \
         patch("core.arxiv_client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        MockClient.return_value.results.return_value = iter(results)
        await fetch_papers(qp)

    # sleep should be called once per paper (except possibly last, but implementation calls it always)
    assert mock_sleep.call_count >= 1


@pytest.mark.asyncio
async def test_fetch_papers_empty_results():
    """Empty arXiv results returns empty list."""
    qp = _make_query()

    with patch("core.arxiv_client.arxiv.Client") as MockClient, \
         patch("core.arxiv_client.asyncio.sleep", new_callable=AsyncMock):
        MockClient.return_value.results.return_value = iter([])
        papers = await fetch_papers(qp)

    assert papers == []


@pytest.mark.asyncio
async def test_fetch_papers_study_period_extraction_called():
    """When study_data_period is set, Claude extraction is triggered."""
    result = _make_arxiv_result()
    qp = _make_query(study_data_period=(date(2010, 1, 1), date(2020, 12, 31)))

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"start_year": 2010, "end_year": 2020}')]

    with patch("core.arxiv_client.arxiv.Client") as MockClient, \
         patch("core.arxiv_client.asyncio.sleep", new_callable=AsyncMock), \
         patch("core.arxiv_client.anthropic.Anthropic") as MockAnthropic:
        MockClient.return_value.results.return_value = iter([result])
        MockAnthropic.return_value.messages.create.return_value = mock_response
        papers = await fetch_papers(qp)

    assert len(papers) == 1
    assert papers[0].study_period_start == date(2010, 1, 1)
    assert papers[0].study_period_end == date(2020, 12, 31)
    MockAnthropic.return_value.messages.create.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_papers_no_study_period_extraction_when_not_requested():
    """When study_data_period is None, Claude is not called."""
    result = _make_arxiv_result()
    qp = _make_query(study_data_period=None)

    with patch("core.arxiv_client.arxiv.Client") as MockClient, \
         patch("core.arxiv_client.asyncio.sleep", new_callable=AsyncMock), \
         patch("core.arxiv_client.anthropic.Anthropic") as MockAnthropic:
        MockClient.return_value.results.return_value = iter([result])
        papers = await fetch_papers(qp)

    MockAnthropic.assert_not_called()
    assert papers[0].study_period_start is None
