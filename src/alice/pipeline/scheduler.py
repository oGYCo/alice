"""Celery Beat schedule configuration for the Alice pipeline.

Defines periodic tasks:
- fetch-all-sources: every 30 minutes (static fallback)
- retry-failed-content: every 1 hour (static fallback)
- get_dynamic_schedule(): reads active sources from DB, adds per-source entries
  with configurable fetch_interval_minutes + random jitter (0-5 min).
"""

import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alice.models.source import Source

# DB-driven schedule: reads active sources from DB, not hardcoded.
# The fetch interval is configurable via the Source model's fetch_interval_minutes.
BEAT_SCHEDULE = {
    "fetch-all-sources": {
        "task": "alice.worker.tasks.task_fetch_all_sources",
        "schedule": 1800.0,  # 30 min
        "options": {"queue": "fetch"},
    },
    "retry-failed-content": {
        "task": "alice.pipeline.tasks.task_retry_failed",
        "schedule": 3600.0,  # 1 hour
        "options": {"queue": "pipeline"},
    },
}


def get_beat_schedule() -> dict:
    """Return the pipeline Celery Beat schedule configuration."""
    return BEAT_SCHEDULE


async def get_dynamic_schedule(session: AsyncSession) -> dict:
    """Build a Celery Beat schedule by reading active sources from DB.

    Returns a dict merging the static fallback entries with per-source entries.
    Each active source gets its own periodic entry keyed as 'fetch-source-{id}'.
    The schedule interval is fetch_interval_minutes + random jitter (0-5 min),
    converted to seconds.
    """
    result = await session.execute(
        select(Source).where(Source.is_active == True)  # noqa: E712
    )
    sources = result.scalars().all()

    schedule: dict = dict(BEAT_SCHEDULE)  # start with static fallback entries

    for source in sources:
        jitter_minutes = random.randint(0, 5)
        interval_seconds = (source.fetch_interval_minutes + jitter_minutes) * 60.0
        schedule[f"fetch-source-{source.id}"] = {
            "task": "alice.worker.tasks.task_fetch_all_sources",
            "schedule": interval_seconds,
            "kwargs": {"source_id": source.id},
            "options": {"queue": "fetch"},
        }

    return schedule
