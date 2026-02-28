# PROJECT KNOWLEDGE BASE

**Generated:** 2026-02-27
**Branch:** main

## OVERVIEW

Alice — AI Secretary: personal intelligent information manager.

- Backend: FastAPI + Celery + SQLAlchemy (async)
- Bot: aiogram webhook service (independent process)
- Frontend: Next.js App Router
- Storage: PostgreSQL + Redis
- Search: Meilisearch
- Graph: Neo4j

## STATUS

Active implementation with backend, bot, frontend, migrations, and tests in-repo.

- Python tests: `tests/unit`, `tests/integration`
- Frontend tests: Vitest + Playwright under `frontend/`
- Prompt templates: root `prompts/*.j2`
- Work plan: `.sisyphus/plans/alice-ai-secretary.md`

## SOURCE OF TRUTH RULE

When docs conflict with code:

1. Code is the source of truth.
2. Fix docs in the same change wave.
3. Do not keep stale architecture claims in docs.

## STRUCTURE (CURRENT)

```text
alice/
├── AGENTS.md
├── README.md
├── DESIGN.md
├── idea.md
├── docker-compose.yml
├── pyproject.toml
├── alembic/
├── prompts/
├── scripts/
├── src/
│   └── alice/
│       ├── api/v1/
│       ├── bot/
│       ├── config/
│       ├── connectors/
│       ├── graph/
│       ├── llm/
│       ├── models/
│       ├── pipeline/
│       ├── schemas/
│       ├── services/
│       ├── worker/
│       ├── db.py
│       ├── main.py
│       └── prompts.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
└── frontend/
    ├── src/
    ├── e2e/
    └── package.json
```

## RUNTIME SERVICES

| Service | Stack | Port |
| --- | --- | --- |
| `api` | FastAPI + Uvicorn | 8000 |
| `bot` | aiogram + aiohttp | 8081 |
| `worker` | Celery worker | - |
| `scheduler` | Celery beat | - |
| `postgres` | PostgreSQL 16 | 5432 |
| `redis` | Redis 7 | 6379 |
| `meilisearch` | Meilisearch | 7700 |
| `neo4j` | Neo4j 5 | 7474 / 7687 |

## AI STACK

| Component | Choice |
| --- | --- |
| Primary LLM | DeepSeek API |
| Local gatekeeper model | Ollama (`qwen2.5:1.5b`) |
| Abstraction | `LLMClient` protocol |
| Test-only mock client | `alice.llm.mock.MockLLMClient` |

## CONVENTIONS

### Python Backend

- Package manager: `uv`
- Lint/format: `ruff`
- Testing: `pytest`
- ORM: SQLAlchemy 2.0 async + Alembic
- Validation: Pydantic v2
- Config: Pydantic Settings (`alice.config`)

### Frontend

- Next.js App Router
- Tailwind + shadcn/ui
- Zustand + TanStack Query
- Vitest + Playwright

### Pipeline

- No Celery chains for stage transitions
- Active stage tasks: `alice.pipeline.tasks`
- Legacy task-name compatibility: `alice.worker.tasks`
- Redis persistence must remain enabled (`appendonly yes`)

## MANDATORY ENGINEERING PRINCIPLES

These are mandatory for all new development and refactors:

1. **Real-environment testing is required**
   - Test-driven work must include real data and real dependencies, not only unit tests.
2. **New modules must be integrated end-to-end**
   - A new module is not complete until it is wired into the existing system flow.
3. **No simulation in production path**
   - Do not use mock/stub logic as runtime business behavior.
4. **Production-grade real configuration only**
   - Configuration must be runnable in real deployment; no fabricated placeholders in runtime defaults.
5. **No TODO-as-delivery**
   - Do not leave TODO comments instead of implementing required functionality.

## ANTI-PATTERNS

**NEVER:**

- Add direct LLM API calls in services (use `LLMClient`)
- Bypass Alembic for schema changes
- Put business logic directly in API routers
- Merge doc claims that are not backed by actual code

**ALWAYS:**

- Add/adjust tests for behavior changes
- Keep Celery task naming/routing aligned between config and modules
- Keep Docker defaults and settings defaults synchronized
- Update docs (`README`/`DESIGN`/`AGENTS`) when interfaces, env vars, or runtime flow changes

## TESTING BASELINE

- Unit tests: fast, isolated, behavior-focused
- Integration tests: must run against real DB/services where applicable
- Frontend E2E: verify user-critical routes and auth flow
- Release gate for major flow changes: at least one non-mocked integration path

## COMMANDS

```bash
# Backend
uv sync --extra dev
uv run ruff check .
uv run pytest
uv run alembic upgrade head
uv run uvicorn alice.main:app --reload

# Docker
docker compose up -d
docker compose logs -f api
docker compose logs -f worker
docker compose down

# Frontend
cd frontend
npm install
npm run dev
npm run lint
npm run test
npm run test:e2e
```

## NOTES

- Content language: Chinese (user-facing) + English (code and concept names)
- Current connector scope: RSS/Atom + arXiv
- Deploy target: both local Docker Compose and cloud VPS

## TASK DECOMPOSITION / GUARDRAILS

### One-Task-Per-Subagent Rule (MANDATORY)

- Each delegation = exactly one atomic task = one file created or modified
- Never ask a subagent to modify multiple files in a single task

### Parallel Execution Rule (MANDATORY)

- Independent tasks must run in parallel
- Independent means: different files and no direct output dependency

## SKILLS

### Available skills

- `skill-creator`: guide for creating or updating skills
  - file: `/Users/ogyco/.codex/skills/.system/skill-creator/SKILL.md`
- `skill-installer`: install curated skills or skills from GitHub path
  - file: `/Users/ogyco/.codex/skills/.system/skill-installer/SKILL.md`

### Skill usage policy

- If a user explicitly names a skill, use it in that turn.
- If a skill file is missing or unreadable, report briefly and continue with best fallback.
- Keep context load minimal: read only the parts needed to execute the task.
