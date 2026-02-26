"""Source management service — CRUD for content sources."""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alice.models.source import Source, SourceType
from alice.schemas.source import SourceConfigSchema


class SourceService:
    """Async CRUD service for Source model."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, config: SourceConfigSchema) -> Source:
        """Create a new content source from config schema."""
        source = Source(
            type=SourceType(config.type),
            name=config.name,
            url=config.url,
            config=config.config,
            is_active=config.enabled,
            fetch_interval_minutes=config.fetch_interval_minutes,
        )
        self._session.add(source)
        await self._session.commit()
        await self._session.refresh(source)
        return source

    async def list_active(self) -> Sequence[Source]:
        """Return all active sources ordered by name."""
        result = await self._session.execute(
            select(Source)
            .where(Source.is_active == True)  # noqa: E712
            .order_by(Source.name.asc())
        )
        return list(result.scalars().all())

    async def mark_fetched(self, source_id: int) -> None:
        """Update last_fetched_at timestamp for a source."""
        result = await self._session.execute(select(Source).where(Source.id == source_id))
        source = result.scalar_one_or_none()
        if source is None:
            raise ValueError(f"Source {source_id} not found")

        source.last_fetched_at = datetime.now(UTC)
        await self._session.commit()

    async def update_source(self, source_id: int, **kwargs) -> Source:
        """Update an existing source with the provided fields.

        Raises ValueError if source not found.
        """
        result = await self._session.execute(select(Source).where(Source.id == source_id))
        source = result.scalar_one_or_none()
        if source is None:
            raise ValueError(f"Source {source_id} not found")

        # Map 'enabled' to the ORM field 'is_active'
        if "enabled" in kwargs:
            kwargs["is_active"] = kwargs.pop("enabled")

        for field, value in kwargs.items():
            setattr(source, field, value)

        await self._session.commit()
        await self._session.refresh(source)
        return source

    async def delete_source(self, source_id: int) -> None:
        """Hard-delete a source by id.

        Raises ValueError if source not found.
        """
        result = await self._session.execute(select(Source).where(Source.id == source_id))
        source = result.scalar_one_or_none()
        if source is None:
            raise ValueError(f"Source {source_id} not found")

        await self._session.delete(source)
        await self._session.commit()
