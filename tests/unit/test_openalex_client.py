import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.openalex_client import (
    _extract_arxiv_id,
    _reconstruct_abstract,
    fetch_papers,
)
from core.models import QueryParameters


def _make_query(
    topic: str = "deskilling labor",
    disciplines: list[str] | None = None,
    max_papers: int = 3,
    pub_start: date = date(2015, 1, 1),
    pub_end: date = date(2026, 1, 1),
) -> QueryParameters:
    return QueryParameters(
        topic=topic,
        disciplines=disciplines or ["economics"],
        publication_date_range=(pub_start, pub_end),
        max_papers=max_papers,
        source="openalex",
    )


def _make_work(
    openalex_id: str = "https://openalex.org/W1234567890",
    title: str = "Craft labor and technological displacement",
    abstract_ii: dict | None = None,
    pub_date: str = "2020-06-15",
    arxiv_url: str | None = None,
    cited_by_count: int = 42,
) -> dict:
    """Build a minimal OpenAlex work dict."""
    if abstract_ii is None:
        abstract_ii = {"This": [0], "is": [1], "an": [2], "abstract": [3]}
    return {
        "id": openalex_id,
        "title": title,
        "abstract_inverted_index": abstract_ii,
        "publication_date": pub_date,
        "ids": {"arxiv": arxiv_url} if arxiv_url else {},
        "authorships": [{"author": {"display_name": "Jane Doe"}}],
        "cited_by_count": cited_by_count,
        "open_access": {"oa_url": "https://example.com/paper.pdf"},
        "primary_location": {},
    }


def _make_httpx_response(works: list[dict], status_code: int = 200) -> MagicMock:
    """Build a mock httpx response."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = {"results": works}
    mock.raise_for_status = MagicMock()
    if status_code >= 400:
        from httpx import HTTPStatusError, Request, Response
        mock.raise_for_status.side_effect = HTTPStatusError(
            "error", request=MagicMock(), response=MagicMock()
        )
    return mock


# --- Unit: _reconstruct_abstract ---

def test_reconstruct_abstract_basic():
    ii = {"Hello": [0], "world": [1]}
    assert _reconstruct_abstract(ii) == "Hello world"


def test_reconstruct_abstract_out_of_order():
    ii = {"world": [1], "Hello": [0]}
    assert _reconstruct_abstract(ii) == "Hello world"


def test_reconstruct_abstract_empty():
    assert _reconstruct_abstract({}) == ""
    assert _reconstruct_abstract(None) == ""


def test_reconstruct_abstract_multiposition():
    ii = {"the": [0, 4], "cat": [1], "sat": [2], "on": [3], "mat": [5]}
    result = _reconstruct_abstract(ii)
    assert result == "the cat sat on the mat"


# --- Unit: _extract_arxiv_id ---

def test_extract_arxiv_id_present():
    ids = {"arxiv": "https://arxiv.org/abs/2301.12345"}
    assert _extract_arxiv_id(ids) == "2301.12345"


def test_extract_arxiv_id_with_version():
    ids = {"arxiv": "https://arxiv.org/abs/2301.12345v2"}
    assert _extract_arxiv_id(ids) == "2301.12345"


def test_extract_arxiv_id_absent():
    assert _extract_arxiv_id({}) is None
    assert _extract_arxiv_id(None) is None


# --- Integration: fetch_papers ---

@pytest.mark.asyncio
async def test_fetch_papers_basic():
    """Basic fetch returns Paper objects."""
    work = _make_work()
    qp = _make_query()

    with patch("core.openalex_client.httpx.AsyncClient") as MockClient, \
         patch("core.openalex_client.asyncio.sleep", new_callable=AsyncMock):
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=_make_httpx_response([work]))
        papers = await fetch_papers(qp)

    assert len(papers) == 1
    assert papers[0].title == "Craft labor and technological displacement"
    assert papers[0].openalex_id == "W1234567890"
    assert papers[0].citation_count == 42


@pytest.mark.asyncio
async def test_fetch_papers_uses_arxiv_id_when_present():
    """Papers with an arXiv ID in ids use it as arxiv_id."""
    work = _make_work(arxiv_url="https://arxiv.org/abs/2301.99999")
    qp = _make_query()

    with patch("core.openalex_client.httpx.AsyncClient") as MockClient, \
         patch("core.openalex_client.asyncio.sleep", new_callable=AsyncMock):
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=_make_httpx_response([work]))
        papers = await fetch_papers(qp)

    assert papers[0].arxiv_id == "2301.99999"
    assert papers[0].openalex_id == "W1234567890"


@pytest.mark.asyncio
async def test_fetch_papers_uses_openalex_id_when_no_arxiv():
    """Papers without arXiv IDs fall back to OpenAlex work ID."""
    work = _make_work(arxiv_url=None)
    qp = _make_query()

    with patch("core.openalex_client.httpx.AsyncClient") as MockClient, \
         patch("core.openalex_client.asyncio.sleep", new_callable=AsyncMock):
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=_make_httpx_response([work]))
        papers = await fetch_papers(qp)

    assert papers[0].arxiv_id == "W1234567890"


@pytest.mark.asyncio
async def test_fetch_papers_date_filter():
    """Papers outside the publication date range are excluded."""
    in_range = _make_work(openalex_id="https://openalex.org/W1", title="In range", pub_date="2020-06-01")
    out_of_range = _make_work(openalex_id="https://openalex.org/W2", title="Out of range", pub_date="2010-01-01")
    qp = _make_query(pub_start=date(2015, 1, 1), pub_end=date(2026, 1, 1))

    with patch("core.openalex_client.httpx.AsyncClient") as MockClient, \
         patch("core.openalex_client.asyncio.sleep", new_callable=AsyncMock):
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=_make_httpx_response([in_range, out_of_range]))
        papers = await fetch_papers(qp)

    assert len(papers) == 1
    assert papers[0].title == "In range"


@pytest.mark.asyncio
async def test_fetch_papers_max_papers_respected():
    """fetch_papers stops at max_papers."""
    works = [_make_work(openalex_id=f"https://openalex.org/W{i}", title=f"Paper {i}") for i in range(10)]
    qp = _make_query(max_papers=3)

    with patch("core.openalex_client.httpx.AsyncClient") as MockClient, \
         patch("core.openalex_client.asyncio.sleep", new_callable=AsyncMock):
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=_make_httpx_response(works))
        papers = await fetch_papers(qp)

    assert len(papers) == 3


@pytest.mark.asyncio
async def test_fetch_papers_http_error_returns_empty():
    """HTTP errors return empty list rather than raising."""
    qp = _make_query()

    with patch("core.openalex_client.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(side_effect=Exception("connection refused"))
        papers = await fetch_papers(qp)

    assert papers == []


@pytest.mark.asyncio
async def test_fetch_papers_skips_work_with_no_title():
    """Works with missing title are skipped."""
    no_title = _make_work(title="")
    valid = _make_work(openalex_id="https://openalex.org/W999", title="Valid paper")
    qp = _make_query()

    with patch("core.openalex_client.httpx.AsyncClient") as MockClient, \
         patch("core.openalex_client.asyncio.sleep", new_callable=AsyncMock):
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=_make_httpx_response([no_title, valid]))
        papers = await fetch_papers(qp)

    assert len(papers) == 1
    assert papers[0].title == "Valid paper"
