from __future__ import annotations

import importlib
from datetime import UTC, datetime
from pathlib import Path

import pytest  # type: ignore

_rss_module = importlib.import_module("alice.connectors.rss")
_source_module = importlib.import_module("alice.schemas.source")

RSSConnector = _rss_module.RSSConnector
SourceConfigSchema = _source_module.SourceConfigSchema


def fixtures_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / "rss_feeds"


async def test_rss_connector_fetch_dedupes_and_normalizes_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connector = RSSConnector()
    feed_xml = fixtures_dir().joinpath("sample_hn.xml").read_text()
    monkeypatch.setattr(connector, "_fetch_feed", lambda _url: feed_xml)
    monkeypatch.setattr(connector, "_extract_full_text", lambda _url: ("Full text", None))

    config = SourceConfigSchema(name="HN", url="https://hnrss.org/frontpage", type="rss")
    results = await connector.fetch(config)

    assert len(results) == 1
    item = results[0]
    assert item.source == "rss"
    assert item.source_url == "https://example.com/post-one"
    assert item.extracted_text == "Full text"
    assert item.extraction_failed is False
    assert item.fetched_at is not None
    assert item.published_at is not None
    assert item.published_at.tzinfo == UTC


async def test_rss_connector_falls_back_to_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    connector = RSSConnector()
    feed_xml = fixtures_dir().joinpath("sample_tech.xml").read_text()
    monkeypatch.setattr(connector, "_fetch_feed", lambda _url: feed_xml)
    monkeypatch.setattr(connector, "_extract_full_text", lambda _url: (None, "blocked"))

    config = SourceConfigSchema(name="Tech", url="https://example.org/feed", type="rss")
    results = await connector.fetch(config)

    assert len(results) == 1
    item = results[0]
    assert item.title == "Atom Entry One"
    assert item.raw_text == "Atom summary text."
    assert item.extracted_text is None
    assert item.extraction_failed is True
    assert item.metadata["extraction_error"] == "blocked"
    assert item.published_at == datetime(2026, 2, 26, 12, 30, 0, tzinfo=UTC)


async def test_rss_connector_skips_entries_without_links(monkeypatch: pytest.MonkeyPatch) -> None:
    connector = RSSConnector()
    feed_xml = fixtures_dir().joinpath("sample_tech.xml").read_text()
    monkeypatch.setattr(connector, "_fetch_feed", lambda _url: feed_xml)
    monkeypatch.setattr(connector, "_extract_full_text", lambda _url: ("Body", None))

    config = SourceConfigSchema(name="Tech", url="https://example.org/feed", type="rss")
    results = await connector.fetch(config)

    assert len(results) == 1
    assert results[0].source_url == "https://example.org/atom-entry"
