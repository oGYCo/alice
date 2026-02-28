"""Tests for Celery worker infrastructure."""

import warnings
from unittest.mock import patch

from alice.worker.celery_app import celery_app
from alice.worker.tasks import (
    task_fetch_all_sources,
    task_push_batch,
    task_run_gatekeeper,
)

import alice.pipeline.tasks as _pipeline_tasks  # noqa: F401 — force registration


def test_celery_app_created():
    """Test that Celery app is created successfully."""
    assert celery_app is not None
    assert celery_app.main == "alice"


def test_celery_broker_configured():
    """Test that broker URL is configured."""
    # The broker should point to Redis
    broker = celery_app.conf.broker_url
    assert broker is not None
    assert "redis" in broker.lower() or "localhost" in broker.lower()


def test_celery_task_routes_configured():
    """Test that pipeline task routes are configured."""
    routes = celery_app.conf.task_routes
    assert "alice.worker.tasks.task_run_gatekeeper" in routes
    assert "alice.worker.tasks.task_run_understanding" in routes
    assert "alice.worker.tasks.task_run_scoring" in routes
    assert "alice.worker.tasks.task_run_indexing" in routes


def test_celery_retry_config():
    """Test that error handling configuration is set."""
    conf = celery_app.conf
    assert conf.task_acks_late is True
    assert conf.task_reject_on_worker_lost is True


def test_legacy_tasks_are_registered():
    """Test that all legacy task names are registered with Celery."""
    registered = celery_app.tasks.keys()
    expected = [
        "alice.worker.tasks.task_run_gatekeeper",
        "alice.worker.tasks.task_run_understanding",
        "alice.worker.tasks.task_run_scoring",
        "alice.worker.tasks.task_run_indexing",
        "alice.worker.tasks.task_fetch_all_sources",
        "alice.worker.tasks.task_push_batch",
    ]
    for task_name in expected:
        assert task_name in registered, f"Task {task_name} not registered"


def test_pipeline_tasks_are_registered():
    """Test that canonical pipeline task names are registered with Celery."""
    registered = celery_app.tasks.keys()
    expected = [
        "alice.pipeline.tasks.task_run_gatekeeper",
        "alice.pipeline.tasks.task_run_understanding",
        "alice.pipeline.tasks.task_run_scoring",
        "alice.pipeline.tasks.task_run_indexing",
        "alice.pipeline.tasks.task_push_batch",
        "alice.pipeline.tasks.task_schedule_push_batches",
        "alice.pipeline.tasks.task_retry_failed",
        "alice.pipeline.tasks.task_batch_update_p_scores",
    ]
    for task_name in expected:
        assert task_name in registered, f"Pipeline task {task_name} not registered"


def test_legacy_wrapper_emits_deprecation_warning():
    """Legacy wrappers emit DeprecationWarning when invoked."""
    expected = {"content_id": 42, "stage": "gatekeeper", "passed": True}
    with patch("alice.pipeline.tasks.task_run_gatekeeper", return_value=expected):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            task_run_gatekeeper.apply(args=[42])
    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert len(deprecations) >= 1
    assert "alice.worker.tasks.task_run_gatekeeper" in str(deprecations[0].message)


def test_task_fetch_returns_summary():
    """Test fetch task returns summary payload (ok or error)."""
    result = task_fetch_all_sources.apply(args=[])
    assert result.result["status"] in {"ok", "error"}
    assert "sources_triggered" in result.result
    assert "items_new" in result.result
    assert "dispatched" in result.result


def test_task_fetch_accepts_source_id_kwarg():
    """Test fetch task accepts source_id for per-source beat entries."""
    result = task_fetch_all_sources.apply(kwargs={"source_id": 7})
    assert result.result["requested_source_id"] == 7


def test_task_push_batch_returns_error_without_chat_id():
    """Legacy push batch returns error since chat_id is unavailable."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        result = task_push_batch.apply(args=[123])
    assert result.result["user_id"] == 123
    assert result.result["status"] == "error"
    assert "error" in result.result


def test_celery_time_limits():
    """Test that time limits are configured."""
    conf = celery_app.conf
    assert conf.task_time_limit == 600  # 10 minutes hard limit
    assert conf.task_soft_time_limit == 540  # 9 minutes soft limit


def test_beat_schedule_configured():
    """Test that Celery Beat schedule is configured."""
    schedule = celery_app.conf.beat_schedule
    assert "fetch-all-sources-every-30-min" in schedule
    assert schedule["fetch-all-sources-every-30-min"]["schedule"] == 1800.0
    assert "retry-failed-every-6-hours" in schedule
    assert schedule["retry-failed-every-6-hours"]["schedule"] == 21600.0
    assert "batch-update-p-scores-daily" in schedule
    assert schedule["batch-update-p-scores-daily"]["schedule"] == 86400.0
    assert "schedule-push-batches" in schedule
    assert schedule["schedule-push-batches"]["schedule"] == 1200.0


def test_celery_serialization_json():
    """Test that JSON serialization is configured."""
    conf = celery_app.conf
    assert conf.task_serializer == "json"
    assert conf.result_serializer == "json"
    assert "json" in conf.accept_content
