"""Alice Celery worker infrastructure."""

from .celery_app import celery_app

__all__ = ["celery_app"]
