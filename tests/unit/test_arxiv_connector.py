from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from alice.connectors.arxiv import ArxivConnector
from alice.schemas.source import SourceConfigSchema


def _make_mock_result(
    entry_id: str,
    title: str,
    summary: str,
    pdf_url: str,
    author_names: list[str],
    published: datetime,
    categories: list[str],
) -> MagicMock:
    result = MagicMock()
    result.entry_id = entry_id
    result.title = title
    result.summary = summary
    result.pdf_url = pdf_url
    result.authors = [MagicMock(name=name) for name in author_names]
    # MagicMock uses 'name' as a special kwarg, so set it explicitly
    for mock_author, name in zip(result.authors, author_names):
        mock_author.name = name
    result.published = published
    result.categories = categories
    return result


def _make_sample_results() -> list[MagicMock]:
    return [
        _make_mock_result(
            entry_id="https://arxiv.org/abs/2301.00001",
            title="Attention Is All You Need: Revisited",
            summary="We revisit the transformer architecture...",
            pdf_url="https://arxiv.org/pdf/2301.00001",
            author_names=["Alice Smith", "Bob Jones"],
            published=datetime(2023, 1, 1, tzinfo=UTC),
            categories=["cs.AI", "cs.LG"],
        ),
        _make_mock_result(
            entry_id="https://arxiv.org/abs/2302.00002",
            title="Scaling Language Models",
            summary="We present an analysis of large language model training dynamics...",
            pdf_url="https://arxiv.org/pdf/2302.00002",
            author_names=["Charlie Brown"],
            published=datetime(2023, 2, 1, tzinfo=UTC),
            categories=["cs.AI", "cs.CL"],
        ),
        _make_mock_result(
            entry_id="https://arxiv.org/abs/2303.00003",
            title="Chain-of-Thought Prompting",
            summary="We explore how chain-of-thought prompting...",
            pdf_url="https://arxiv.org/pdf/2303.00003",
            author_names=["Frank Miller"],
            published=datetime(2023, 3, 15, tzinfo=UTC),
            categories=["cs.AI", "cs.CL", "cs.LG"],
        ),
    ]


async def test_arxiv_connector_returns_correct_count() -> None:
    """Connector returns the same number of results as the mock client produces."""
    sample_results = _make_sample_results()

    with patch("alice.connectors.arxiv.arxiv.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.results.return_value = iter(sample_results)

        connector = ArxivConnector()
        config = SourceConfigSchema(
            name="test",
            url="cat:cs.AI",
            type="arxiv",
            config={"max_results": 3},
        )
        results = await connector.fetch(config)

    assert len(results) == 3


async def test_arxiv_connector_maps_fields_correctly() -> None:
    """First result has all fields mapped to RawContentSchema correctly."""
    sample_results = _make_sample_results()

    with patch("alice.connectors.arxiv.arxiv.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.results.return_value = iter(sample_results)

        connector = ArxivConnector()
        config = SourceConfigSchema(
            name="test",
            url="cat:cs.AI",
            type="arxiv",
            config={"max_results": 3},
        )
        results = await connector.fetch(config)

    item = results[0]
    assert item.source_url == "https://arxiv.org/abs/2301.00001"
    assert item.source_id == "https://arxiv.org/abs/2301.00001"
    assert item.title == "Attention Is All You Need: Revisited"
    assert item.raw_text == "We revisit the transformer architecture..."
    assert item.author == "Alice Smith, Bob Jones"
    assert item.metadata["pdf_url"] == "https://arxiv.org/pdf/2301.00001"
    assert item.metadata["categories"] == ["cs.AI", "cs.LG"]


async def test_arxiv_connector_sets_source_field() -> None:
    """All results have source set to 'arxiv'."""
    sample_results = _make_sample_results()

    with patch("alice.connectors.arxiv.arxiv.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.results.return_value = iter(sample_results)

        connector = ArxivConnector()
        config = SourceConfigSchema(
            name="test",
            url="cat:cs.AI",
            type="arxiv",
        )
        results = await connector.fetch(config)

    assert all(item.source == "arxiv" for item in results)


async def test_arxiv_connector_sets_published_at() -> None:
    """published_at is populated from the arxiv result's published datetime."""
    sample_results = _make_sample_results()

    with patch("alice.connectors.arxiv.arxiv.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.results.return_value = iter(sample_results)

        connector = ArxivConnector()
        config = SourceConfigSchema(
            name="test",
            url="cat:cs.AI",
            type="arxiv",
        )
        results = await connector.fetch(config)

    assert results[0].published_at == datetime(2023, 1, 1, tzinfo=UTC)
    assert results[1].published_at == datetime(2023, 2, 1, tzinfo=UTC)
    assert results[2].published_at == datetime(2023, 3, 15, tzinfo=UTC)


async def test_arxiv_connector_uses_default_max_results() -> None:
    """Connector passes max_results=20 when config.config has no max_results key."""
    import arxiv as arxiv_module

    with patch("alice.connectors.arxiv.arxiv.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.results.return_value = iter([])

        with patch("alice.connectors.arxiv.arxiv.Search") as mock_search_cls:
            connector = ArxivConnector()
            config = SourceConfigSchema(
                name="test",
                url="cat:cs.LG",
                type="arxiv",
            )
            await connector.fetch(config)

        mock_search_cls.assert_called_once_with(
            query="cat:cs.LG",
            max_results=20,
            sort_by=arxiv_module.SortCriterion.SubmittedDate,
        )
