"""Celery Beat schedule configuration."""

# Beat schedule configuration
# This is used by celery_app.py and merged into beat_schedule
BEAT_SCHEDULE = {
    "fetch-all-sources-every-30-min": {
        "task": "alice.worker.tasks.task_fetch_all_sources",
        "schedule": 1800.0,  # 30 minutes in seconds
        "options": {"queue": "fetch"},
    },
}


def get_beat_schedule() -> dict:
    """Return the Celery Beat schedule configuration."""
    return BEAT_SCHEDULE
