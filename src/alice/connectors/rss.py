from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from time import struct_time
from typing import Protocol, TypedDict, cast
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import feedparser  # type: ignore
import httpx  # type: ignore[import-untyped]
import structlog  # type: ignore[import-untyped]
import trafilatura  # type: ignore[import-untyped]

from ..schemas.content import RawContentSchema
from ..schemas.source import SourceConfigSchema
from .base import BaseConnector


class Logger(Protocol):
    def error(self, event: str, **kwargs: object) -> None: ...

    def warning(self, event: str, **kwargs: object) -> None: ...


logger = cast(Logger, structlog.get_logger())


class LinkItem(TypedDict, total=False):
    href: str


class ContentItem(TypedDict, total=False):
    value: str


class AuthorDetail(TypedDict, total=False):
    name: str


class FeedEntry(TypedDict, total=False):
    link: str
    links: list[LinkItem]
    id: str
    guid: str
    title: str
    summary: str
    description: str
    content: list[ContentItem]
    author: str
    author_detail: AuthorDetail
    published_parsed: struct_time
    updated_parsed: struct_time
    language: str


class FeedData(TypedDict):
    entries: list[FeedEntry]
    feed: dict[str, object]


class FeedParserLike(Protocol):
    entries: list[object]
    feed: dict[object, object]


class RSSConnector(BaseConnector):
    _tracking_params: set[str] = {"fbclid", "ref"}
    _default_headers: dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(self) -> None:
        super().__init__()

    async def fetch(self, config: SourceConfigSchema) -> list[RawContentSchema]:
        config_map = cast(dict[str, object], config.config)
        request_headers = self._build_request_headers(config_map.get("headers"))
        feed_xml = await self._fetch_feed(config.url, request_headers)
        parsed = self._parse_feed(feed_xml)
        fetched_at = datetime.now(UTC)

        results: list[RawContentSchema] = []
        seen_urls: set[str] = set()
        limit_value = config_map.get("limit")
        limit = limit_value if isinstance(limit_value, int) else None

        for entry in parsed["entries"]:
            source_url = self._get_entry_link(entry)
            if not source_url:
                continue

            normalized_url = self._normalize_url(source_url)
            if normalized_url in seen_urls:
                continue
            seen_urls.add(normalized_url)

            summary = self._get_entry_summary(entry)
            full_text, error = await self._extract_full_text(normalized_url)

            extraction_failed = full_text is None
            if extraction_failed:
                raw_text = summary
            else:
                raw_text = summary or full_text

            metadata: dict[str, object] = {}
            if error:
                metadata["extraction_error"] = error

            item = RawContentSchema(
                source=config.type,
                source_url=normalized_url,
                source_id=self._get_entry_id(entry),
                title=self._get_entry_text(entry, "title"),
                raw_text=raw_text,
                extracted_text=full_text,
                author=self._get_entry_author(entry),
                published_at=self._get_entry_published_at(entry),
                fetched_at=fetched_at,
                language=self._get_entry_text(entry, "language")
                or self._get_feed_text(parsed["feed"], "language"),
                metadata=metadata,
                extraction_failed=extraction_failed,
            )
            results.append(item)

            if limit is not None and len(results) >= limit:
                break

        return results

    def _build_request_headers(self, custom_headers: object) -> dict[str, str]:
        headers = dict(self._default_headers)
        if isinstance(custom_headers, dict):
            for key, value in custom_headers.items():
                if isinstance(key, str) and isinstance(value, str):
                    headers[key] = value
        return headers

    async def _fetch_feed(self, url: str, headers: dict[str, str] | None = None) -> str:
        request_headers = headers or self._default_headers
        try:
            async with httpx.AsyncClient(
                timeout=20.0,
                follow_redirects=True,
            ) as client:
                response = await client.get(
                    url,
                    headers=request_headers,
                )
                _ = response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error(
                "rss_fetch_failed",
                url=url,
                error=str(exc),
                headers=request_headers,
            )
            raise
        return response.text

    async def _extract_full_text(self, url: str) -> tuple[str | None, str | None]:
        try:
            html = await asyncio.to_thread(trafilatura.fetch_url, url)
            if not html:
                return None, "empty_html"
            extracted = await asyncio.to_thread(trafilatura.extract, html)
            if not extracted:
                return None, "no_extracted_text"
            return extracted.strip(), None
        except Exception as exc:  # noqa: BLE001
            logger.warning("rss_extract_failed", url=url, error=str(exc))
            return None, "extract_exception"

    def _normalize_url(self, url: str) -> str:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        if hostname.startswith("www."):
            hostname = hostname[4:]

        query_params: list[tuple[str, str]] = []
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            if key.startswith("utm_"):
                continue
            if key in self._tracking_params:
                continue
            query_params.append((key, value))

        normalized_query = urlencode(query_params)
        normalized = parsed._replace(
            netloc=hostname if not parsed.port else f"{hostname}:{parsed.port}",
            query=normalized_query,
        )
        return urlunparse(normalized)

    def _get_entry_link(self, entry: FeedEntry) -> str | None:
        candidates: list[str] = []
        link = entry.get("link")
        if link:
            candidates.append(link)
        links = entry.get("links")
        if isinstance(links, list):
            for item in links:
                href = item.get("href")
                if href:
                    candidates.append(href)

        for candidate in candidates:
            parsed = urlparse(candidate)
            if parsed.scheme in {"http", "https"}:
                return candidate
        return None

    def _get_entry_id(self, entry: FeedEntry) -> str | None:
        return entry.get("id") or entry.get("guid")

    def _get_entry_author(self, entry: FeedEntry) -> str | None:
        author = self._get_entry_text(entry, "author")
        if author:
            return author
        author_detail = entry.get("author_detail") or {}
        name = author_detail.get("name")
        if isinstance(name, str):
            return name
        return None

    def _get_entry_summary(self, entry: FeedEntry) -> str | None:
        summary = self._get_entry_text(entry, "summary") or self._get_entry_text(
            entry, "description"
        )
        if summary:
            return summary
        content = entry.get("content")
        if isinstance(content, list) and content:
            value = content[0].get("value")
            if isinstance(value, str):
                return value
        return None

    def _get_entry_published_at(self, entry: FeedEntry) -> datetime | None:
        parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
        if not parsed_time:
            return None
        return datetime(
            parsed_time.tm_year,
            parsed_time.tm_mon,
            parsed_time.tm_mday,
            parsed_time.tm_hour,
            parsed_time.tm_min,
            parsed_time.tm_sec,
            tzinfo=UTC,
        )

    def _get_entry_text(self, entry: FeedEntry, key: str) -> str | None:
        value = entry.get(key)
        if isinstance(value, str):
            return value
        return None

    def _get_feed_text(self, feed: dict[str, object], key: str) -> str | None:
        value = feed.get(key)
        if isinstance(value, str):
            return value
        return None

    def _parse_feed(self, feed_xml: str) -> FeedData:
        parsed = feedparser.parse(feed_xml)  # type: ignore
        parsed = cast(FeedParserLike, cast(object, parsed))
        return FeedData(
            entries=cast(list[FeedEntry], parsed.entries),
            feed=cast(dict[str, object], parsed.feed),
        )
