"""Celery Beat schedule configuration for the Alice pipeline.

Defines periodic tasks:
- fetch-all-sources: every 30 minutes
- retry-failed-content: every 1 hour
"""

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
