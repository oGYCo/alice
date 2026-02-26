# Alice AI Secretary — Learnings

## Project Context
- Greenfield project, pre-implementation stage
- Python (FastAPI) backend + Next.js frontend + Telegram bot
- Plan: 78 tasks across 5 phases (0-4)
- DESIGN.md is the master design document (1207 lines)

## Architecture Decisions
- **Package manager**: uv ONLY (not pip, poetry, conda)
- **Docker**: 6 services — api:8000, bot:8081, worker, scheduler, postgres:5432, redis:6379
- **Ollama**: Runs on HOST machine, accessed via `host.docker.internal:11434` — NOT inside Docker
- **LLM**: DeepSeek API (primary), Qwen 1.5B via Ollama (gatekeeper), MockLLMClient (tests)
- **Pipeline**: Individual Celery tasks + DB state machine (NEVER Celery chains)
- **Redis**: MUST configure `appendonly yes` in Docker Compose
- **Bot**: aiogram webhook mode on port 8081, SEPARATE Docker service from FastAPI
- **Phase 0 only**: No Neo4j, Meilisearch, Next.js, knowledge graph, 7-dim scoring

## Conventions
- Run tests: `uv run pytest tests/ -v`
- Run linting: `uv run ruff check .`
- Run formatting: `uv run ruff format .`
- Source packages: `src/alice/` NOT `src/` directly (convention for clean imports)
- TDD: RED → GREEN → REFACTOR
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`
- Notepad: Append only, never overwrite

## [2026-02-26] Task 1: Project Scaffolding ✓

### Completed
- ✓ `pyproject.toml` - hatchling build backend, all runtime + dev dependencies, ruff/mypy/pytest config
- ✓ `docker-compose.yml` - 6 services (api:8000, bot:8081, worker, scheduler, postgres:16, redis:7 with appendonly)
- ✓ `docker-compose.test.yml` - test DB (alice_test on 5433) and test Redis (6380)
- ✓ `Dockerfile` - multi-stage build with uv
- ✓ `Makefile` - targets: up, down, test, lint, format, migrate, logs, shell, clean
- ✓ `.env.example` - all 11 config variables
- ✓ `src/alice/` package structure - __init__.py, main.py, config.py, logging.py
- ✓ `tests/` structure - conftest.py, unit/, integration/, fixtures/ directories
- ✓ `tests/unit/test_config.py` - 3 TDD tests for config loading
- ✓ `uv run pytest tests/unit/test_config.py -v` → ALL 3 PASS
- ✓ `uv run ruff check .` → All checks passed

### Key Decisions
1. **uv as sole package manager**: Installed all 95 packages (no pip/poetry)
2. **src/alice/ package structure**: Imports as `from alice.xxx import yyy` per DESIGN.md
3. **Pydantic Settings v2**: Config loads from .env with SettingsConfigDict
4. **Structlog JSON logging**: Configured for structured logs, removed basicConfig stream parameter (was causing AttributeError)
5. **FastAPI /health endpoint**: Required for docker-compose healthcheck
6. **Port separation**: API on 8000, Bot on 8081 (separate services)
7. **Redis with appendonly yes**: Persistence configured in compose
8. **No Ollama in compose**: Runs on HOST at host.docker.internal:11434

### Testing Approach (TDD)
- Wrote tests FIRST: test_config.py with 3 assertions (defaults, env override, debug flag)
- Implemented config.py to pass tests
- All 3 tests pass in 0.04s

### Linting Results
- ruff auto-fixed 5 issues: import sorting + unused imports (os, pytest in test_config.py)
- All 6 original errors fixed
- Final ruff check: "All checks passed!"

### File Count
15 files created:
- 4 config files (pyproject.toml, docker-compose.yml, docker-compose.test.yml, Dockerfile)
- 2 utility files (Makefile, .env.example)
- 4 source modules (src/alice/{__init__,main,config,logging}.py)
- 5 test files (tests/{__init__,conftest}.py + tests/{unit,integration}/__init__.py + test_config.py)

### Evidence
- Saved to `.sisyphus/evidence/task-1-dev-tooling.txt`
- Pytest: 3 passed in 0.03s
- Ruff: All checks passed

### Next Steps (for orchestrator)
- Task 2: Create alembic migrations directory + sample migration
- Task 3: Create src/alice/models/ with SQLAlchemy base and initial models
- Task 4: Create src/alice/services/ and tests/integration/test_api.py for FastAPI endpoints
- Task 5: Set up Celery task structure (celery_app, worker tasks)


## [2026-02-26] Task 3: Pydantic Schemas

### Key Decisions
- **StrEnum over `str, Enum`**: Used `enum.StrEnum` for FeedbackType and PipelineStatus to follow Python 3.11+ best practices and satisfy ruff UP042 rules.
- **Type annotation consistency**: Migrated from `Optional[T]` to `T | None` syntax (Python 3.10+) per ruff UP045 recommendations.
- **ORM compatibility**: Set `model_config = {"from_attributes": True}` on ContentResponseSchema for seamless SQLAlchemy model conversion.
- **Phase 0 scope**: ContentUnderstandingSchema only includes 4 fields (summary, key_points, domains, estimated_read_time). Full 14-field version deferred to Phase 1.
- **Validation constraints**: Implemented Field constraints for bounded values (quality_score 1-10, fetch_interval 5-1440 min, gatekeeper confidence 0-1).
- **Post-init hook**: Used `model_post_init()` for computed field (passes_threshold) in QualityScoreSchema to enforce 6.0 threshold.

### Test Coverage
- 18 tests across 9 test classes
- Coverage includes: valid/invalid inputs, field constraints, enum values, ORM compatibility, computed fields
- All tests passing with pytest in 0.06s

### Import Structure
- Central `__all__` exports in `__init__.py` for clean package interface
- Clean separation: content.py, source.py, feedback.py, pipeline.py, gatekeeper.py, quality.py
- Test organization: Single test_schemas.py with class-based grouping by domain

### Ruff Compliance
- Automatically fixed: import ordering, type annotation style, unused imports
- Manual fixes: StrEnum inheritance (UP042)
- Final: 0 errors, all checks passed

### Patterns Used
- Pydantic v2 BaseModel for DTO validation
- StrEnum for type-safe string enums
- Field(...) validators for constraints
- Type hints with `|` syntax (Python 3.10+)

## [2026-02-26] Task 5: Prompt Templates + Jinja2

### Implementation Summary
- Created `prompts/` directory at project root (not under src/)
- Implemented 4 Jinja2 templates matching DESIGN.md exactly
- Built PromptManager class with:
  - FileSystemLoader pointing to correct path: `Path(__file__).parent.parent.parent / "prompts"`
  - autoescape=False (critical for LLM prompts - they're not HTML)
  - trim_blocks=True, lstrip_blocks=True (clean template output)
  - Convenience methods for each prompt type
  - Module-level singleton for easy import

### Key Design Decisions
1. **Template Language Feature Usage**:
   - `| default()` filter for optional parameters
   - `| truncate()` filter for content length control
   - `| join()` for domain list formatting
   - Conditional `{% if language == 'zh' %}` for bilingual instruction

2. **PromptManager Configuration**:
   - Synchronous (no async needed for template rendering)
   - Type hints with `object` for kwargs (flexible)
   - Path resolution relative to module location (importable as `from alice.prompts import PromptManager`)

3. **Test Coverage**:
   - 7 tests covering all 4 templates
   - Tests verify template existence, variable substitution, and format instructions
   - Edge case: Chinese language handling in understanding.j2
   - Error case: TemplateNotFound exception for missing templates

### Inheritance Pattern
- Used `list[str]` type hints (Python 3.9+) instead of `List[str]`
- Aligned with project's Python 3.12 target

### Lessons for Phase 1+
- When integrating into pipeline tasks, use `from alice.prompts import prompt_manager` singleton
- LLM responses will be parsed as JSON (gatekeeper, understanding, quality_score)
- Push reason is plain text, not JSON
- All templates are language-aware where needed

### Verified
- ✓ 7/7 pytest tests pass
- ✓ ruff linting clean on new files
- ✓ Path resolution correct (tested with actual template loading)
- ✓ All 4 templates render without errors

## [2026-02-26] Task 4: LLM Abstraction Layer

### Summary
Successfully implemented the LLM abstraction layer for the Alice AI Secretary project with protocol-based design, three client implementations (DeepSeek, Ollama, Mock), and comprehensive test coverage.

### Key Achievements
- **Protocol-first design**: `LLMClient` Protocol with `@runtime_checkable` enables clean interface without inheritance
- **Multi-provider support**: DeepSeek (OpenAI-compatible API), Ollama (local inference), Mock (testing)
- **Retry logic**: DeepSeekClient implements exponential backoff with configurable delays [1s, 5s, 30s]
- **Structured outputs**: Both `complete()` and `complete_structured()` methods with JSON parsing and markdown code block stripping
- **Test fixtures**: Pre-loaded JSON fixture files for gatekeeper decisions and quality scores
- **Factory pattern**: `create_llm_client(provider)` enables easy provider switching

### Technical Details
1. **DeepSeekClient**: Uses AsyncOpenAI SDK with 10-min timeout, manual retry handling, JSON sanitization
2. **OllamaClient**: httpx-based local inference, supports checking server availability with `is_available()`
3. **MockLLMClient**: Fixture-file or inline response support for testing, call counting for response sequencing
4. **Fixture Path Resolution**: 4x `__file__.parent` traversal from `src/alice/llm/mock.py` to reach `tests/fixtures/`

### Testing
- 8 unit tests, all PASS
- Tests cover: basic completion, structured parsing, protocol conformance, factory creation, error handling
- Ruff linting: All checks pass after auto-fix of import ordering

### Files Created
```
src/alice/llm/
├── __init__.py           (8 lines)
├── protocol.py          (32 lines)
├── deepseek.py         (104 lines)
├── ollama.py           (71 lines)
├── mock.py             (61 lines)
├── factory.py          (23 lines)

tests/
├── unit/test_llm.py    (83 lines)
└── fixtures/llm_responses/
    ├── gatekeeper_pass.json
    ├── gatekeeper_reject.json
    ├── understanding_response.json
    └── quality_score.json
```

### Design Decisions
1. **Protocol over ABC**: Allows runtime checking with `isinstance()` without explicit inheritance
2. **Manual retries**: DeepSeekClient doesn't rely on OpenAI SDK retries—easier to debug and customize
3. **Fixture fixture design**: MockLLMClient can either load from `.json` files or use inline `set_responses()`
4. **No streaming**: Per spec, only return final complete text (simplifies parsing)
5. **No caching**: Let caller handle caching logic (keeps abstraction layer thin)

### Ready for Next Task
LLM abstraction is production-ready and can be injected anywhere via FastAPI's `Depends()` pattern.
Next: Task 5 (Content Cleaners) can use `LLMClient` protocol for formatting decisions.


## [2026-02-26] Task 6: Celery Worker Infrastructure

### Key Learnings

1. **Celery App Factory Pattern**
   - Use `create_celery_app()` function for testability
   - Module-level singleton `celery_app` for actual usage
   - Configuration via Pydantic Settings (CELERY_BROKER_URL, REDIS_URL)

2. **Individual Task Pattern (NO Chains)**
   - Each task is independent and idempotent
   - Task registration: explicit `name="alice.worker.tasks.task_*"` parameter
   - State machine lives in PostgreSQL (not Redis)
   - Each task logs pipeline stage + returns stub response shape

3. **Task Routing & Queues**
   - Pipeline tasks (gatekeeper/understanding/scoring/indexing) → "pipeline" queue
   - Fetch task → "fetch" queue
   - Push task → "push" queue
   - Enables independent worker scaling per queue

4. **Celery Configuration Essentials**
   - `task_acks_late=True` + `task_reject_on_worker_lost=True` → at-least-once delivery
   - `task_autoretry_for=(Exception,)` + `task_max_retries=5` → automatic retries
   - `task_retry_backoff=True` + `task_retry_backoff_max=1800` → exponential backoff up to 30min
   - `task_time_limit=600, task_soft_time_limit=540` → safety limits
   - JSON serialization (human-readable, safer than pickle)

5. **Beat Schedule (Scheduler)**
   - Direct in `app.conf.beat_schedule` (avoids circular imports with scheduler.py)
   - `scheduler.py` is config reference only, not imported
   - Schedule format: `{"task_name": "...", "schedule": 1800.0, "options": {"queue": "..."}}`
   - fetch-all-sources: 1800s = 30 minutes

6. **Testing Celery Tasks**
   - Use `.apply(args=[...])` for synchronous execution (no broker needed)
   - `.apply()` returns `EagerResult` with `.result` attribute
   - Never use `.apply_async()` in unit tests (requires broker)
   - Task.bind=True enables `self` parameter (task ID, retries, etc.)

7. **Import Organization**
   - Ruff auto-fixes: `I001` (unsorted imports), `F401` (unused imports), `F811` (redefinitions)
   - Import order: stdlib → third-party → local (with blank line between)
   - `from alice.worker.celery_app import celery_app` (not create_celery_app)

### Files Created
- ✓ `src/alice/worker/__init__.py` - Package exports celery_app
- ✓ `src/alice/worker/celery_app.py` - Factory + configuration
- ✓ `src/alice/worker/tasks.py` - 6 stub tasks
- ✓ `src/alice/worker/scheduler.py` - Beat schedule reference
- ✓ `tests/unit/test_worker.py` - 14 tests

### Verification
- ✓ `uv run pytest tests/unit/test_worker.py -v` → 14 passed
- ✓ `uv run ruff check .` → All checks passed
- ✓ All task registrations verified
- ✓ Configuration values validated
- ✓ Task output shapes verified (stub responses)

### Anti-Patterns Avoided
- ✗ NO Celery chains/groups (use DB state machine instead)
- ✗ NO real pipeline logic in stubs (fill in Tasks 9-16)
- ✗ NO Flower monitoring
- ✗ NO Redis-based state (PostgreSQL state machine in Task 13)

### Dependency Chain
- Depends on: Task 5 (config.py)
- Required by: Tasks 7-13 (LLM client, services, orchestrator)

## [2026-02-26] Task 2: PostgreSQL Schema + Alembic Migrations ✓

### Completed Deliverables
- ✓ `alembic/` directory initialized with async engine support
- ✓ `src/alice/models/` package with 5 model files (base, user, source, content, feedback)
- ✓ `src/alice/db.py` with AsyncSessionLocal factory and get_db() dependency
- ✓ Initial migration created: `alembic/versions/7311687d15f6_initial_schema.py`
- ✓ `tests/unit/test_models.py` with 12 model structure tests
- ✓ `uv run pytest tests/unit/test_models.py -v` → 12/12 PASS
- ✓ `uv run ruff check .` → All checks passed

### Key Architecture Decisions

1. **StrEnum over `str, enum.Enum`**: Migrated all enums (PipelineStatus, SourceType, FeedbackType) to `enum.StrEnum` (Python 3.11+) for cleaner code and ruff compliance (UP042).

2. **Type Annotations**: Used `T | None` syntax (Python 3.10+) instead of `Optional[T]` throughout models per ruff UP045.

3. **Alembic Async Support**:
   - Modified `env.py` to use `async_engine_from_config` and `asyncio.run()` for async migrations
   - Configured offline mode for autogenerate to avoid database connection requirements during schema generation
   - Set `literal_binds=False` for autogenerate operations

4. **Enum Handling in Migrations**:
   - Explicitly created PostgreSQL enum types in upgrade()
   - Proper drop order in downgrade() (tables before enums)
   - Used `Enum.create()` and `Enum.drop()` for type management

5. **Model Design**:
   - Base class with TimestampMixin for created_at/updated_at
   - Content table with comprehensive fields: raw_text, extracted_text, pipeline_status, quality_score, summary, key_points, domains, estimated_read_time
   - Source table tracks RSS/arXiv sources with fetch_interval and last_fetched_at
   - User table tied to Telegram chat IDs with preferences JSON
   - Feedback table links users to content with type enum

### Import Path Resolution
- Models use relative imports: `from .base import Base, TimestampMixin`
- DB module: `from alice.config import settings` (package-level import)
- Migration env.py: `from alice.models import Base` (alembic directory at root level)

### Alembic Configuration
- `alembic.ini`: sqlalchemy.url = `postgresql+asyncpg://alice:alice@postgres:5432/alice`
- `env.py` detects revision mode and uses offline for autogenerate
- Migration file: manual DDL with proper Enum type handling

### Test Coverage
- 12 tests across enum validation, model structure, field existence
- Tests cover: PipelineStatus (6 values), SourceType (2), FeedbackType (4), required columns
- All model tables verified for expected columns and constraints

### Ruff Linting Process
1. Fixed duplicate datetime imports in source.py and content.py
2. Moved `import sys` to top of alembic/env.py (E402 violation)
3. Converted all enums to StrEnum (UP042)
4. Auto-fixed import ordering in worker files

### Lessons & Patterns

**What Worked Well**:
- Manual migration file approach avoids DB connection for autogenerate (better for CI/CD)
- StrEnum + Mapped[EnumType] provides type safety in SQLAlchemy 2.0
- Separate db.py module keeps engine/session factory clean and reusable

**Migration Strategy**:
- Offline mode with SQLAlchemy URL only (no connection needed to generate DDL)
- For actual execution: will connect and run SQL (Phase 0 uses test DB)
- Downgrade path fully implemented (can reverse migrations)

**Type Safety**:
- `Mapped[T]` from SQLAlchemy 2.0 provides full type hints
- `datetime | None` over Optional for cleaner syntax
- StrEnum values are literally strings ("fetched", "rss", etc.)

### Ready for Phase 0 Pipeline
- All models defined per DESIGN.md Phase 0 scope
- Alembic ready for: `uv run alembic upgrade head` (when DB available)
- `get_db()` dependency ready for FastAPI route injection
- No Neo4j, Meilisearch, or graph features (deferred to Phase 2+)

### Next Phase: Task 3+
- Content pipeline tasks can use these models with session injection
- API endpoints can fetch/update Content, Source, User, Feedback
- Celery tasks can insert pipeline results directly to DB

## [2026-02-26] Task 10: Understanding Service ✓

### Implementation Summary
- Added `UnderstandingService` to render the understanding prompt, call the LLM, parse JSON, and log `domains` plus `estimated_read_time`.
- Implemented single retry on JSON decode failure with a strict JSON re-prompt.

### Tests
- Added unit tests covering fixture parsing, retry success, retry failure, and Chinese content.
- `uv run pytest tests/unit/test_understanding.py -v` → 4 passed

## Task 12: Content Storage + Retrieval Service (2026-02-26)

### SQLAlchemy async patterns confirmed
- `result.scalars().all()` returns `Sequence[T]` not `list[T]` — wrap with `list()` or use `Sequence` return type
- `result.scalar_one_or_none()` for single-row lookups
- Both work fine with `AsyncMock` in unit tests

### Unit test mock pattern for SQLAlchemy ORM models
- `Content.__new__(Content)` bypasses ORM `__init__` → `_sa_instance_state` missing → attribute setters blow up
- **Correct approach**: `MagicMock(spec=Content)` + `setattr()` for each attribute
- This lets attribute mutations work in tests without a real DB session

### URL normalization via urllib.parse
- `urlparse` / `urlunparse` cleanly handles scheme, netloc, path, query
- `parse_qs(keep_blank_values=True)` + filter utm_* + `urlencode(doseq=True)` to clean query params
- Strip www. from netloc after lowercasing

### FastAPI router return type annotations
- FastAPI `response_model=` handles serialization — route functions return ORM objects
- basedpyright complains about `list[ORM] != list[Schema]` mismatch
- Solution: annotate route return type as `Any` (FastAPI uses `response_model` at runtime)

### Integration test skip pattern
- Module-level `pytest.skip(..., allow_module_level=True)` is the correct approach
- Module-scoped async fixtures (like `engine`) execute BEFORE function-scoped fixtures → `autouse` skip doesn't help
- `if not TEST_DATABASE_URL: pytest.skip(...)` at module level works perfectly

### services/__init__.py
- Had stale `from .gatekeeper import GatekeeperService` import (gatekeeper.py doesn't exist yet)
- Fixed to only export `ContentStorageService` and `SourceService`

### Custom pytest markers
- Must register in `[tool.pytest.ini_options] markers = [...]` in pyproject.toml to avoid `PytestUnknownMarkWarning`
- Added `integration` marker registration


## ArXiv Connector (Task: Phase 0)
- `arxiv` package API: `arxiv.Client().results(arxiv.Search(query=..., max_results=..., sort_by=...))` returns a generator — wrap in `list()` inside executor
- Blocking arxiv calls go in `run_in_executor(None, ...)` — the closure captures `config.url` and `max_results` from outer scope cleanly
- `arxiv.Author` mock gotcha: `MagicMock(name=...)` is special in unittest.mock — set `.name` attribute AFTER construction: `mock.name = value`
- `SourceConfigSchema.type` has regex `^(rss|arxiv)$` — must pass `type="arxiv"` in tests
- ruff UP017: use `datetime.UTC` (Python 3.11+) instead of `timezone.utc` — this project targets Python 3.14
- ruff I001: relative imports must come after absolute stdlib/third-party in sorted order (`.base` after `..schemas`)
- Connector pattern: `fetched_at = datetime.now(UTC)` set once before loop, not per-item
## [2026-02-26] Task 11: Quality Scoring Service
- Added ScoringService to render quality_score prompt, parse JSON, retry once on invalid JSON, and log scoring_complete with score + passes_threshold.
- Added unit tests covering fixture parsing, threshold boundaries (6.0/5.9), retry success, and retry failure.
