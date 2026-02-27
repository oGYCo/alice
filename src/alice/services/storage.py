"""Content storage service — CRUD + pipeline state transitions."""

from collections.abc import Sequence
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from alice.models.content import Content, PipelineStatus
from alice.models.feedback import Feedback
from alice.schemas.content import RawContentSchema


def normalize_url(url: str) -> str:
    """Normalize URL for deduplication.

    - Lowercase scheme + host
    - Remove www. prefix
    - Strip trailing slash from path
    - Remove utm_* query parameters
    """
    parsed = urlparse(url)

    # Lowercase scheme and host, strip www.
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]

    # Strip trailing slash from path
    path = parsed.path.rstrip("/") if parsed.path != "/" else parsed.path

    # Remove utm_* params
    if parsed.query:
        qs = parse_qs(parsed.query, keep_blank_values=True)
        filtered = {k: v for k, v in qs.items() if not k.startswith("utm_")}
        query = urlencode(filtered, doseq=True)
    else:
        query = ""

    normalized = urlunparse((scheme, netloc, path, parsed.params, query, ""))
    return normalized


class ContentStorageService:
    """Async CRUD service for Content model with URL deduplication."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def store_raw(self, raw: RawContentSchema) -> Content:
        """Insert new content, skip if URL already exists (dedup).

        Returns the existing or newly created Content.
        """
        normalized = normalize_url(raw.source_url)

        # Check for existing content with normalized URL
        result = await self._session.execute(
            select(Content).where(Content.source_url == normalized)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        content = Content(
            source=raw.source,
            source_url=normalized,
            source_id=raw.source_id,
            title=raw.title,
            raw_text=raw.raw_text,
            extracted_text=raw.extracted_text,
            author=raw.author,
            published_at=raw.published_at,
            fetched_at=raw.fetched_at,
            language=raw.language,
            metadata_=raw.metadata,
            pipeline_status=PipelineStatus.fetched,
        )
        self._session.add(content)
        await self._session.commit()
        await self._session.refresh(content)
        return content

    async def get_by_id(self, content_id: int) -> Content | None:
        """Fetch content by primary key."""
        result = await self._session.execute(select(Content).where(Content.id == content_id))
        return result.scalar_one_or_none()

    async def update_pipeline_status(
        self,
        content_id: int,
        status: PipelineStatus,
        error: str | None = None,
    ) -> None:
        """Update pipeline_status (and optionally pipeline_error) for a content item."""
        content = await self._get_or_raise(content_id)
        content.pipeline_status = status
        if error is not None:
            content.pipeline_error = error
        await self._session.commit()

    async def update_understanding(
        self,
        content_id: int,
        summary: str,
        key_points: list[str],
        domains: list[str],
        read_time: int,
        content_type: str | None = None,
    ) -> None:
        """Store LLM understanding results and advance status to 'understood'."""
        content = await self._get_or_raise(content_id)
        content.summary = summary
        content.key_points = key_points
        content.domains = domains
        content.estimated_read_time = read_time
        content.pipeline_status = PipelineStatus.understood
        if content_type is not None:
            meta = dict(content.metadata_) if content.metadata_ else {}
            meta["content_type"] = content_type
            content.metadata_ = meta
        await self._session.commit()

    async def update_score(
        self,
        content_id: int,
        score: float,
        reasoning: str,
    ) -> None:
        """Store quality score and advance status to 'scored'.

        Note: reasoning is stored as pipeline_error field is for errors only;
        we store it in summary prefix or simply ignore as non-model field.
        The model has no 'scoring_reasoning' column — we store score + status.
        """
        content = await self._get_or_raise(content_id)
        content.quality_score = score
        content.pipeline_status = PipelineStatus.scored
        await self._session.commit()

    async def get_pending(
        self,
        stage: PipelineStatus,
        limit: int = 50,
    ) -> Sequence[Content]:
        """Return up to `limit` content items at the given pipeline stage."""
        result = await self._session.execute(
            select(Content)
            .where(Content.pipeline_status == stage)
            .order_by(Content.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_content(
        self,
        *,
        status: PipelineStatus | None = None,
        limit: int = 20,
        offset: int = 0,
        sort: str = "newest",
    ) -> Sequence[Content]:
        """List content with optional status filter, pagination, and basic sort.

        Uses load_only to avoid selecting optional/newer columns that may not
        exist on databases that have not applied every migration yet.
        """
        query: Select[tuple[Content]] = select(Content).options(
            load_only(
                Content.id,
                Content.source,
                Content.source_url,
                Content.title,
                Content.pipeline_status,
                Content.quality_score,
                Content.summary,
                Content.key_points,
                Content.domains,
                Content.estimated_read_time,
                Content.metadata_,
                Content.created_at,
            )
        )

        if status is not None:
            query = query.where(Content.pipeline_status == status)

        if sort == "oldest":
            query = query.order_by(Content.created_at.asc())
        elif sort == "relevance":
            query = query.order_by(
                Content.quality_score.desc().nullslast(),
                Content.created_at.desc(),
            )
        else:
            query = query.order_by(Content.created_at.desc())

        result = await self._session.execute(query.offset(offset).limit(limit))
        return list(result.scalars().all())

    async def get_pushable(
        self,
        min_score: float = 6.0,
        limit: int = 20,
    ) -> Sequence[Content]:
        """Return scored content above min_score, ordered by score descending."""
        result = await self._session.execute(
            select(Content)
            .where(
                Content.pipeline_status == PipelineStatus.scored,
                Content.quality_score >= min_score,
            )
            .order_by(Content.quality_score.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_or_raise(self, content_id: int) -> Content:
        result = await self._session.execute(select(Content).where(Content.id == content_id))
        content = result.scalar_one_or_none()
        if content is None:
            raise ValueError(f"Content {content_id} not found")
        return content

    async def delete_by_id(self, content_id: int) -> bool:
        """Delete a single content item by id. Returns True if deleted, False if not found."""
        # Remove dependent feedback rows first to satisfy FK constraint
        await self._session.execute(
            delete(Feedback).where(Feedback.content_id == content_id)
        )
        result = await self._session.execute(
            delete(Content).where(Content.id == content_id)
        )
        await self._session.commit()
        return result.rowcount > 0  # type: ignore[return-value]

    async def delete_batch(self, ids: list[int]) -> int:
        """Delete multiple content items by ids. Returns count of deleted rows."""
        if not ids:
            return 0
        # Remove dependent feedback rows first to satisfy FK constraint
        await self._session.execute(
            delete(Feedback).where(Feedback.content_id.in_(ids))
        )
        result = await self._session.execute(
            delete(Content).where(Content.id.in_(ids))
        )
        await self._session.commit()
        return result.rowcount  # type: ignore[return-value]
