# Issues / Gotchas — alice-ai-secretary

## [2026-02-26] Wave 0.1 Issues

1. **Python 3.14.2** — uv resolved 3.14.2 not 3.12. No issues so far.
2. **structlog stream param** — `basicConfig(stream=...)` causes AttributeError. Solution: remove stream param.
3. **Circular imports in Celery** — putting beat_schedule in scheduler.py causes circular import with celery_app.py. Solution: put directly in celery_app.py.
4. **Alembic offline mode** — Use offline mode for migration generation to avoid needing live DB.
5. **Subagents marked plan checkboxes** — Subagents may self-mark checkboxes; orchestrator must verify and re-mark correctly.
