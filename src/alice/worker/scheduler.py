"""Celery Beat schedule configuration."""

# Beat schedule configuration
# This is used by celery_app.py and merged into beat_schedule
BEAT_SCHEDULE = {
    "fetch-all-sources-every-30-min": {
        "task": "alice.worker.tasks.task_fetch_all_sources",
        "schedule": 1800.0,  # 30 minutes in seconds
        "options": {"queue": "fetch"},
    },
    "retry-failed-every-6-hours": {
        "task": "alice.pipeline.tasks.task_retry_failed",
        "schedule": 21600.0,  # 6 hours
        "options": {"queue": "pipeline"},
    },
    "batch-update-p-scores-daily": {
        "task": "alice.pipeline.tasks.task_batch_update_p_scores",
        "schedule": 86400.0,  # 24 hours
        "options": {"queue": "pipeline"},
    },
    "schedule-push-batches": {
        "task": "alice.pipeline.tasks.task_schedule_push_batches",
        "schedule": 1200.0,  # 20 minutes
        "options": {"queue": "push"},
    },
    "retry-failed-graph-extractions-every-12-hours": {
        "task": "alice.pipeline.tasks.task_retry_failed_graph_extractions",
        "schedule": 43200.0,  # 12 hours
        "options": {"queue": "pipeline"},
    },
}


def get_beat_schedule() -> dict:
    """Return the Celery Beat schedule configuration."""
    return BEAT_SCHEDULE
