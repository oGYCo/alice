"""Celery application factory and configuration."""

from celery import Celery

from alice.config import settings


def create_celery_app() -> Celery:
    """Create and configure Celery application."""
    app = Celery(
        "alice",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.REDIS_URL,
        include=["alice.worker.tasks"],
    )

    app.conf.update(
        # Task behavior
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        # Error handling
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        # Retry config
        task_autoretry_for=(Exception,),
        task_max_retries=5,
        task_retry_backoff=True,
        task_retry_backoff_max=1800,  # max 30 minutes
        # Time limits
        task_time_limit=600,  # 10 minutes hard limit
        task_soft_time_limit=540,  # 9 minutes soft limit
        # Routes
        task_routes={
            "alice.worker.tasks.task_run_gatekeeper": {"queue": "pipeline"},
            "alice.worker.tasks.task_run_understanding": {"queue": "pipeline"},
            "alice.worker.tasks.task_run_scoring": {"queue": "pipeline"},
            "alice.worker.tasks.task_run_indexing": {"queue": "pipeline"},
            "alice.worker.tasks.task_fetch_all_sources": {"queue": "fetch"},
            "alice.worker.tasks.task_push_batch": {"queue": "push"},
        },
        # Beat schedule
        beat_schedule={
            "fetch-all-sources-every-30-min": {
                "task": "alice.worker.tasks.task_fetch_all_sources",
                "schedule": 1800.0,  # 30 minutes in seconds
                "options": {"queue": "fetch"},
            },
        },
        beat_schedule_filename="celerybeat-schedule",
        timezone="UTC",
        # Result expiry
        result_expires=3600,  # 1 hour
    )

    return app


# Module-level app instance
celery_app = create_celery_app()
