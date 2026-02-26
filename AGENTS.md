# PROJECT KNOWLEDGE BASE

**Generated:** 2026-02-26
**Commit:** 8a7c38e
**Branch:** main

## OVERVIEW

Alice — AI Secretary: personal intelligent information manager. Python (FastAPI) backend + Next.js frontend + Telegram bot. Pre-implementation stage: no source code yet, only DESIGN.md and work plan.

## STATUS

**Pre-implementation.** No source code exists. The project plan lives at `.sisyphus/plans/alice-ai-secretary.md` (58 tasks, 5 phases). Execute with `/start-work`.

## STRUCTURE (PLANNED)

```
alice/
├── DESIGN.md              # Master design doc (1207 lines) — source of truth
├── README.md              # Original requirements (Chinese)
├── AGENTS.md              # This file
├── .sisyphus/
│   └── plans/
│       └── alice-ai-secretary.md  # Work plan (58 tasks, Phases 0-4)
├── Folo/                  # REFERENCE project only (gitignored). DO NOT modify.
│
│  === PLANNED DIRECTORIES (created by plan tasks) ===
│
├── docker-compose.yml     # 6 services: api, bot, worker, scheduler, postgres, redis
├── pyproject.toml         # Python project config (uv + ruff + pytest)
├── src/
│   ├── alice/
│   │   ├── api/           # FastAPI app + routers
│   │   ├── bot/           # aiogram Telegram bot (separate service, port 8081)
│   │   ├── connectors/    # Content source plugins (RSS, arXiv, etc.)
│   │   ├── pipeline/      # Content processing: cleaner → parser → scorer → indexer
│   │   ├── models/        # SQLAlchemy ORM models + Alembic migrations
│   │   ├── services/      # Business logic layer
│   │   ├── tasks/         # Celery task definitions (individual tasks, NOT chains)
│   │   ├── graph/         # Knowledge graph (Neo4j, Phase 2+)
│   │   ├── llm/           # LLM client abstraction (protocol + mock)
│   │   ├── prompts/       # Jinja2 prompt templates
│   │   └── config.py      # Pydantic Settings
│   └── tests/             # pytest (TDD)
├── frontend/              # Next.js app (Phase 2+)
│   ├── src/
│   │   ├── app/           # App Router pages
│   │   ├── components/    # React components (shadcn/ui)
│   │   └── lib/           # Utilities, API client
│   └── package.json
└── alembic/               # Database migrations
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Architecture decisions | `DESIGN.md` | Master design doc, ALL features spec'd |
| Work plan / task list | `.sisyphus/plans/alice-ai-secretary.md` | 58 tasks across 5 phases |
| UI patterns reference | `Folo/apps/desktop/layer/renderer/` | Card UI, feed layout, glassmorphic design |
| Component patterns | `Folo/packages/internal/components/` | Reusable component structure |
| DB schema patterns | `Folo/packages/internal/database/src/schemas/` | Drizzle ORM (Alice uses SQLAlchemy instead) |
| Folo conventions | `Folo/AGENTS.md` | Monorepo conventions (reference only) |

## ARCHITECTURE DECISIONS (FINAL)

### Services (Docker Compose)

| Service | Stack | Port | Notes |
|---------|-------|------|-------|
| `api` | FastAPI + Uvicorn | 8000 | Main REST API |
| `bot` | aiogram (webhook mode) | 8081 | Separate from API. DO NOT embed in FastAPI |
| `worker` | Celery | — | Content pipeline tasks |
| `scheduler` | Celery Beat | — | Periodic fetching |
| `postgres` | PostgreSQL 16 | 5432 | Primary datastore |
| `redis` | Redis 7 (`appendonly yes`) | 6379 | Broker + cache. MUST configure persistence |

### AI Stack

| Component | Choice | Notes |
|-----------|--------|-------|
| Primary LLM | **DeepSeek API** | ~$0.22/1000 items, 10-min timeout |
| Gatekeeper (local) | **Qwen 1.5B via Ollama** | On RTX 4060 Laptop (~1.2GB VRAM). NOT 7B |
| Ollama access | `host.docker.internal` | Runs on HOST, not inside Docker |
| LLM abstraction | `LLMClient` protocol | With `MockLLMClient` for tests |
| Prompt management | Jinja2 templates in `prompts/` | — |

### Data Stack

| Component | Phase | Notes |
|-----------|-------|-------|
| PostgreSQL | 0+ | Primary store, state machine for pipeline |
| Redis | 0+ | Celery broker, caching. `appendonly yes` |
| Neo4j | **2+ ONLY** | Knowledge graph. DO NOT include before Phase 2 |
| Meilisearch | **1+ ONLY** | Full-text search. DO NOT include in Phase 0 |
| Vector DB | **NEVER** | Alice does NOT use vector databases |

## CONVENTIONS

### Python Backend
- **Package manager**: uv (NOT pip, NOT poetry)
- **Linting/formatting**: ruff
- **Testing**: pytest (TDD — red/green/refactor)
- **ORM**: SQLAlchemy 2.0 async + Alembic migrations
- **Validation**: Pydantic v2 for all DTOs
- **Dependency injection**: FastAPI `Depends()` for LLM client, DB sessions
- **Config**: Pydantic Settings from environment variables

### Frontend (Phase 2+)
- **Framework**: Next.js App Router
- **UI library**: shadcn/ui
- **State**: Zustand + TanStack Query
- **Testing**: vitest
- **Graph visualization**: React Flow (NOT D3 directly)
- **Style reference**: Folo's glassmorphic design system (see `Folo/apps/desktop/AGENTS.md`)

### Content Pipeline
- **Task execution**: Individual Celery tasks with PostgreSQL-backed state machine
- **RSS extraction**: trafilatura for full-text (RSS feeds truncated ~90% of time)
- **Language normalization**: English canonical concept names, Chinese aliases
- **Gatekeeper fallback**: Rule-based fallback when Ollama is down

## ANTI-PATTERNS (THIS PROJECT)

**NEVER:**
- Use **Celery chains** — they abort on first failure. Use individual tasks + DB state machine
- Use **Neo4j GDS** (Leiden/PageRank) — requires Enterprise Edition. Use Python-side NetworkX + leidenalg
- Use **vector databases** — Alice uses GraphRAG, not RAG
- Run **Ollama inside Docker** — runs on host, access via `host.docker.internal`
- Include **Neo4j in Phase 0 or 1** — Phase 2+ only
- Include **Meilisearch in Phase 0** — Phase 1+ only
- Build **Next.js frontend in Phase 0** — Phase 2+ only (Telegram-only in Phase 0-1)
- Use **7B models** on the laptop — only 1.5B/3B fit RTX 4060 Laptop GPU
- Use `as any` or `@ts-ignore` in TypeScript
- Write over-abstracted "enterprise" patterns — solo developer project, keep it simple
- Add inline comments that restate code — comments explain WHY, not WHAT

**ALWAYS:**
- Write tests FIRST (TDD)
- Use `LLMClient` protocol (never call LLM APIs directly)
- Configure Redis with `appendonly yes` (prevent data loss)
- Use Pydantic models for API request/response
- Use Alembic for ALL schema changes

## FOLO REFERENCE PROJECT

`Folo/` is a **read-only reference** (gitignored). It's the RSSNext/Folo RSS reader — a pnpm monorepo (Electron + React Native + SSR). Alice borrows:

- **UI patterns**: Card-based feed layout, glassmorphic depth system, Apple UIKit color tokens
- **Component structure**: Shared packages pattern (`packages/internal/`)
- **Data model patterns**: Content entries, feeds, subscriptions (but Alice uses Python/SQLAlchemy, not TypeScript/Drizzle)

Folo has its own AGENTS.md files — do NOT modify them. They document Folo's conventions, not Alice's.

## COMMANDS

```bash
# No commands yet — project is pre-implementation
# After Phase 0 Task 1, these will exist:

# Backend
uv sync                           # Install Python deps
uv run pytest                     # Run tests
uv run alembic upgrade head       # Run migrations
uv run uvicorn alice.api.main:app # Start API server

# Docker
docker compose up -d              # Start all 6 services
docker compose logs -f worker     # Watch pipeline logs

# Frontend (Phase 2+)
cd frontend && pnpm install       # Install frontend deps
cd frontend && pnpm dev           # Start dev server
cd frontend && pnpm vitest        # Run frontend tests
```

## NOTES

- **Solo developer** using multi-agent parallel development (OpenCode + Sisyphus orchestrator)
- **Deployment**: Both local Docker Compose AND cloud VPS supported
- **DESIGN.md has 9 known inconsistencies** — Task 18 in the plan addresses these
- **Content language**: Chinese (user-facing) + English (code, concept names)
- **MVP content sources**: RSS/Atom + arXiv only (Phase 0). More connectors in Phase 1+4
