"""Celery application factory and configuration."""

from celery import Celery
from celery.signals import worker_process_init

from alice.config import settings


@worker_process_init.connect
def reset_db_pool(**kwargs: object) -> None:
    """Reinitialise the SQLAlchemy engine in each forked worker process.

    Celery uses prefork; child processes inherit the parent's asyncpg
    connections and event-loop state.  Using NullPool here means every
    task creates its own fresh connection and closes it afterwards, which
    completely avoids "Future attached to a different loop" and
    InterfaceError races.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    import alice.db as db_module

    # Abandon (don't try to close) inherited connections from the parent process.
    db_module.engine.sync_engine.dispose(close=False)
    db_module.engine = create_async_engine(
        settings.DATABASE_URL, poolclass=NullPool, echo=settings.DEBUG
    )
    db_module.AsyncSessionLocal = async_sessionmaker(
        db_module.engine, class_=AsyncSession, expire_on_commit=False
    )


def create_celery_app() -> Celery:
    """Create and configure Celery application."""
    app = Celery(
        "alice",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.REDIS_URL,
        include=["alice.worker.tasks", "alice.pipeline.tasks"],
    )

    app.conf.update(
        # Task behavior
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        # Error handling
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        # Time limits
        task_time_limit=600,  # 10 minutes hard limit
        task_soft_time_limit=540,  # 9 minutes soft limit
        # Routes
        task_routes={
            "alice.pipeline.tasks.task_run_gatekeeper": {"queue": "pipeline"},
            "alice.pipeline.tasks.task_run_understanding": {"queue": "pipeline"},
            "alice.pipeline.tasks.task_run_scoring": {"queue": "pipeline"},
            "alice.pipeline.tasks.task_run_indexing": {"queue": "pipeline"},
            "alice.pipeline.tasks.task_retry_failed": {"queue": "pipeline"},
            "alice.pipeline.tasks.task_batch_update_p_scores": {"queue": "pipeline"},
            "alice.pipeline.tasks.task_kg_feedback_update": {"queue": "pipeline"},
            "alice.pipeline.tasks.task_push_batch": {"queue": "push"},
            # Legacy compatibility routes (old stub task names).
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
        },
        beat_schedule_filename="celerybeat-schedule",
        timezone="UTC",
        # Result expiry
        result_expires=3600,  # 1 hour
    )

    return app


# Module-level app instance
celery_app = create_celery_app()
