# Alice — AI Secretary: Project Development Plan (Phase 0-4)

## TL;DR

> **Quick Summary**: Build an AI-powered personal information management system that collects content from RSS/arXiv (MVP), processes it through a 4-stage LLM pipeline, maintains a personal knowledge graph (GraphRAG), and delivers ranked content via Telegram Bot and Web Dashboard. Architecture: Python (FastAPI) backend + Next.js frontend, DeepSeek API + local Qwen 1.5B gatekeeper, PostgreSQL + Neo4j + Meilisearch + Redis.
>
> **Deliverables**:
> - Phase 0: Docker-based backend with RSS+arXiv connectors, LLM pipeline, Telegram bot push+feedback
> - Phase 1: Quality scoring engine, push ranking, time-window scheduling, Meilisearch search
> - Phase 2: Neo4j knowledge graph, GraphRAG, content-subgraph matching, Next.js web dashboard
> - Phase 3: FSRS spaced repetition, user state machine, auto reports, advanced feedback skills
> - Phase 4: Additional connectors (10+), ε-greedy exploration, QA flow, knowledge graph visualization
>
> **Estimated Effort**: XL (multi-month, phased delivery)
> **Parallel Execution**: YES — 5-8 tasks per wave within each phase
> **Critical Path**: Infrastructure → DB+Alembic → Connectors → Gatekeeper → Understanding → Storage → Telegram Bot → Feedback → Integration Tests

---

## Context

### Original Request
Build "Alice — AI Secretary", a personal AI-powered information management system that filters, ranks, and delivers high-quality content based on the user's personal knowledge graph. The system should act as a true AI secretary that knows what the user understands, what they lack, and what they're currently working on, then uses this understanding to precisely filter, rank, and push the most valuable content from 14+ information sources via Telegram Bot and a web dashboard.

### Interview Summary
**Key Discussions**:
- **Tech Stack**: Python (FastAPI) backend + Next.js frontend — confirmed by user
- **Python Tooling**: Use `uv` as the only Python package/runtime manager (`uv sync`, `uv add`, `uv run`) — confirmed by user
- **AI Provider**: DeepSeek API as primary LLM (cost-effective, ~$0.22/1000 items) — confirmed by user
- **Gatekeeper**: Local Qwen 1.5B/3B on RTX 4060 Laptop via Ollama — confirmed by user (NOT 7B as in original DESIGN.md)
- **MVP Sources**: RSS/Atom + arXiv only (not 14+ connectors) — confirmed by user
- **Deployment**: Both local (Docker Compose) and cloud (VPS) — confirmed by user
- **Testing**: TDD with pytest (backend) + vitest (frontend) — confirmed by user
- **Developer**: Solo developer using multi-agent parallel development — confirmed by user
- **Scope**: Complete Phase 0-4 roadmap in ONE plan — confirmed by user

**Research Findings**:
- **Folo UI**: Two-column layout, card patterns with metadata+title+excerpt, Radix UI + Tailwind, list/grid views, declarative settings — applicable patterns for Alice's web dashboard
- **Folo Data**: Drizzle ORM, feeds/entries/subscriptions tables, Readability content extraction — good reference for content modeling
- **GraphRAG**: Neo4j GraphRAG Python lib for retrieval, Leiden community detection (requires Python-side via NetworkX, NOT Neo4j GDS which is Enterprise-only), Personalized PageRank, hybrid search (graph 50% + text 30% + semantic 20%)
- **FSRS**: Free Spaced Repetition Scheduler — modern replacement for Ebbinghaus, mature Python library (`fsrs` v5.1.3)
- **Telegram**: aiogram v3 (Python async) for bot, webhook mode on separate port from FastAPI, rate limits (30 msgs/sec per bot, 1/sec per user)
- **Pipeline**: Celery individual tasks with DB-backed state machine (NOT chains — chains abort on first failure), Redis with AOF persistence

### Metis Review
**Identified Gaps** (all addressed):
- **Neo4j GDS licensing**: Leiden/PageRank algorithms require Enterprise Edition. **Resolution**: Use Python-side algorithms (NetworkX + leidenalg) — batch operations, acceptable overhead
- **RSS full-text extraction**: RSS feeds provide truncated content ~90% of time. **Resolution**: Add trafilatura extraction step in connectors
- **aiogram process architecture**: Must run as separate Docker service from FastAPI, webhook mode on port 8081. **Resolution**: Explicit Docker service architecture
- **LLM prompt management**: 8+ distinct prompt chains need versioning. **Resolution**: `prompts/` directory with Jinja2 templates
- **Content language normalization**: Chinese+English concepts need canonical names. **Resolution**: Normalize to English canonical names, store Chinese aliases
- **Celery chain fragility**: Chains abort on failure. **Resolution**: Individual tasks with DB-backed state machine
- **Redis data loss**: Without persistence, queued tasks lost on restart. **Resolution**: Configure `appendonly yes`
- **Gatekeeper fallback**: Laptop sleeping or Ollama crashed. **Resolution**: Rule-based fallback filter
- **Docker→Host Ollama**: Container needs host access. **Resolution**: `host.docker.internal` or `--network=host`
- **DESIGN.md inconsistencies**: 9 items to update (Qwen version, AI provider, FSRS, Leiden, aiogram, MVP scope, etc.)

---

## Work Objectives

### Core Objective
Build a complete, phased AI information management system that evolves from a simple "RSS→filter→summarize→Telegram push" pipeline (Phase 0) to a fully intelligent knowledge-graph-driven personal secretary (Phase 4), with strict incremental delivery and TDD discipline.

### Concrete Deliverables
- Phase 0: Working Docker Compose stack with 6 services, 2 connectors, 4-stage pipeline, Telegram bot
- Phase 1: Quality scoring engine, push ranking formula, Meilisearch integration, time-window scheduling
- Phase 2: Neo4j knowledge graph, GraphRAG queries, content-subgraph matching, Next.js dashboard
- Phase 3: FSRS spaced repetition, user cognitive model, auto reports, advanced feedback skills
- Phase 4: 10+ connectors, ε-greedy exploration, QA dialog flow, knowledge graph visualization, export

### Definition of Done
- [ ] `docker compose up -d` starts all services healthy
- [ ] RSS connector fetches and extracts full-text content
- [ ] arXiv connector fetches papers by category
- [ ] Gatekeeper filters low-quality content (local Qwen or rule-based fallback)
- [ ] DeepSeek processes content into structured understanding
- [ ] Telegram bot pushes ranked content with feedback buttons
- [ ] Feedback updates user preferences in database
- [ ] `uv run pytest tests/ -v` passes with 100% on all implemented phases
- [ ] Each phase has end-to-end smoke test passing

### Must Have
- Docker Compose deployment (local + cloud VPS compatible)
- RSS/Atom + arXiv connectors with full-text extraction (trafilatura)
- 4-stage content pipeline with DB-backed state machine (NOT Celery chains)
- Local Qwen 1.5B gatekeeper via Ollama with rule-based fallback
- DeepSeek API for content understanding with retry logic
- Telegram bot (aiogram webhook) with push + feedback
- PostgreSQL with Alembic migrations (user_id FK everywhere for future multi-tenant)
- Python dependency/runtime managed by `uv` only (no mixed toolchains)
- TDD: pytest for backend, vitest for frontend
- LLM abstraction layer (LLMClient protocol + MockLLMClient for tests)
- Structured logging via structlog
- Prompt management via Jinja2 templates in `prompts/` directory

### Must NOT Have (Guardrails)
- ❌ Vector database (explicit DESIGN.md constraint)
- ❌ Neo4j/Meilisearch in Phase 0 (Phase 1-2 only)
- ❌ Next.js frontend in Phase 0 (Phase 2 only)
- ❌ 7-dimension quality scoring in Phase 0 (single LLM score only)
- ❌ Content subgraph generation in Phase 0 (Phase 2 only)
- ❌ Celery chains for pipeline orchestration (use individual tasks)
- ❌ Connector plugin framework / over-engineered abstractions
- ❌ Skill engine for feedback routing (simple if/else until Phase 3)
- ❌ Ollama inside Docker (runs on host, accessed via host.docker.internal)
- ❌ Neo4j GDS library (use Python-side NetworkX + leidenalg instead)
- ❌ Over-engineering: no universal query layers, no configuration frameworks, no abstract factories
- ❌ Mixed Python environment managers (`pip`/`venv`/`poetry`/`pdm`) in project workflow

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.
> Acceptance criteria requiring "user manually tests/confirms" are FORBIDDEN.

### Test Decision
- **Infrastructure exists**: NO (greenfield project)
- **Automated tests**: TDD (pytest backend, vitest frontend)
- **Framework**: pytest (backend), vitest (frontend)
- **Setup**: pytest + pytest-asyncio + httpx (TestClient) for backend, vitest + @testing-library/react for frontend
- **If TDD**: Each task follows RED (failing test) → GREEN (minimal impl) → REFACTOR

### Python Tooling Policy
- Use `uv` as the single Python entrypoint for dependency install, lock/sync, and command execution.
- Run Python commands as `uv run <command>` (for example: `uv run pytest`, `uv run ruff`, `uv run mypy`, `uv run python`).
- Do NOT add `requirements.txt`-driven workflows or parallel package managers.

### QA Policy
Every task MUST include agent-executed QA scenarios (see TODO template below).
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Backend API**: Use Bash (curl) — Send requests, assert status + response fields
- **Pipeline/Workers**: Use Bash — Trigger pipeline, check DB state via API
- **Telegram Bot**: Use Bash (curl to webhook endpoint with mock updates) — assert bot behavior via API
- **Frontend/UI (Phase 2+)**: Use Playwright (playwright skill) — Navigate, interact, assert DOM, screenshot
- **Docker Services**: Use Bash (docker compose) — Health checks, log inspection

### Mock Strategy
- All LLM calls via `LLMClient` protocol with dependency injection
- `MockLLMClient` returns fixture data from `tests/fixtures/`
- Fixtures: sample RSS XML, arXiv API responses, DeepSeek response JSON, Ollama response JSON
- Integration tests use real Docker services (PostgreSQL, Redis) via test compose file
- Telegram tests use aiogram's built-in test utilities with mocked updates

---

## Execution Strategy

### Phase Overview

```
Phase 0 — MVP Foundation (Weeks 1-3): "Dumb but Working" E2E Pipeline
  RSS → Gatekeeper → Understanding → Score → Storage → Telegram Push → Feedback
  Infrastructure: Docker, PostgreSQL, Redis, Alembic, Celery, structlog
  No: Neo4j, Meilisearch, Next.js, knowledge graph, complex scoring

Phase 1 — Intelligence Layer (Weeks 4-6): Quality + Ranking + Search
  7-dimension quality scoring formula
  Push priority ranking (P_score formula)
  Meilisearch full-text search integration
  Time-window push scheduling
  Enhanced Telegram cards
  Content deduplication (SimHash)

Phase 2 — Knowledge Engine (Weeks 7-10): GraphRAG + Web Dashboard
  Neo4j knowledge graph setup
  Content subgraph generation
  User knowledge graph modeling
  Content-user matching (prerequisite coverage)
  Next.js web dashboard (feed view, settings, content detail)
  GraphRAG hybrid queries

Phase 3 — Cognitive System (Weeks 11-14): Memory + Repetition + Reports
  FSRS spaced repetition engine
  3-tier memory system (working/short-term/long-term)
  User state machine (daily/project/explore modes)
  Auto weekly/monthly report generation
  Advanced feedback skill system
  Leiden community detection for concept clustering

Phase 4 — Full Vision (Weeks 15-20): Scale + Explore + Visualize
  10+ additional connectors (X, Reddit, GitHub, YouTube, 微信公众号, etc.)
  ε-greedy exploration mechanism
  "Explain concept" QA dialog flow
  Knowledge graph interactive visualization (React Flow)
  Content export (Markdown, PDF)
  Admin panel + analytics dashboard
  Performance optimization + caching
```

### Parallel Execution Waves

> Maximize throughput by grouping independent tasks into parallel waves.
> Each wave completes before the next begins.
> Target: 5-8 tasks per wave. Fewer than 3 per wave (except final) = under-splitting.

```
=== PHASE 0: MVP Foundation ===

Wave 0.1 (Start Immediately — infrastructure + scaffolding):
├── Task 1: Project scaffolding + Docker Compose + dev tooling [quick]
├── Task 2: PostgreSQL schema + Alembic setup [quick]
├── Task 3: Pydantic models + shared types [quick]
├── Task 4: LLM abstraction layer (LLMClient protocol + Mock) [quick]
├── Task 5: Prompt templates directory + Jinja2 setup [quick]
└── Task 6: Celery + Redis worker infrastructure [quick]

Wave 0.2 (After 0.1 — connectors + gatekeeper, MAX PARALLEL):
├── Task 7: RSS/Atom connector with trafilatura extraction (depends: 2,3) [deep]
├── Task 8: arXiv connector (depends: 2,3) [deep]
├── Task 9: Gatekeeper service - Ollama + rule-based fallback (depends: 3,4,5) [deep]
├── Task 10: Content understanding service - DeepSeek (depends: 3,4,5) [deep]
├── Task 11: Quality scoring - simple LLM score (depends: 3,4,5) [quick]
└── Task 12: Content storage + retrieval service (depends: 2,3) [unspecified-high]

Wave 0.3 (After 0.2 — pipeline + bot + integration):
├── Task 13: Pipeline orchestrator - DB-backed state machine (depends: 6,7-12) [deep]
├── Task 14: Telegram bot service - aiogram webhook (depends: 2,3,12) [unspecified-high]
├── Task 15: Celery Beat scheduling + source management API (depends: 1,6,12) [quick]
└── Task 16: Telegram push service - content delivery (depends: 12,14,15) [quick]

Wave 0.4 (After 0.3 — E2E verification):
├── Task 17: Integration tests + E2E smoke test (depends: all Phase 0) [deep]
└── Task 18: DESIGN.md updates - fix 9 inconsistencies (depends: none) [writing]

=== PHASE 1: Intelligence Layer ===

Wave 1.1 (After Phase 0 — scoring + ranking):
├── Task 19: 7-dimension quality scoring formula (depends: 11) [deep]
├── Task 20: Push priority ranking engine (P_score formula) (depends: 12) [deep]
├── Task 21: Meilisearch integration + full-text indexing (depends: 12) [unspecified-high]
├── Task 22: Content deduplication - URL normalization + SimHash (depends: 12) [unspecified-high]
└── Task 23: Enhanced Telegram card formatting (depends: 14) [quick]

Wave 1.2 (After 1.1 — scheduling + integration):
├── Task 24: Time-window push scheduling (depends: 20) [deep]
├── Task 25: Search API endpoints (depends: 21) [quick]
└── Task 26: Phase 1 integration tests (depends: 19-25) [deep]

=== PHASE 2: Knowledge Engine ===

Wave 2.1 (After Phase 1 — graph + frontend scaffolding):
├── Task 27: Neo4j setup + schema + Python driver (depends: Phase 1) [unspecified-high]
├── Task 28: Content subgraph generation via LLM (depends: 10,27) [deep]
├── Task 29: Next.js project scaffolding + API client (depends: Phase 1) [quick]
├── Task 30: Next.js auth + layout shell (depends: 29) [visual-engineering]
└── Task 31: User knowledge graph - initial model (depends: 27) [deep]

Wave 2.2 (After 2.1 — matching + UI pages):
├── Task 32: Content-user matching algorithm (depends: 28,31) [ultrabrain]
├── Task 33: GraphRAG hybrid query engine (depends: 27,21) [deep]
├── Task 34: Feed view page - cards + list/grid (depends: 30) [visual-engineering]
├── Task 35: Content detail page + reading view (depends: 30) [visual-engineering]
├── Task 36: Settings page - sources, preferences, schedule (depends: 30) [visual-engineering]
└── Task 37: Knowledge graph update on feedback (depends: 31,15) [deep]

Wave 2.3 (After 2.2 — integration):
├── Task 38: Phase 2 integration tests (depends: 32-37) [deep]
└── Task 39: Frontend tests - vitest + Playwright (depends: 34-36) [unspecified-high]

=== PHASE 3: Cognitive System ===

Wave 3.1 (After Phase 2 — memory + repetition):
├── Task 40: FSRS spaced repetition engine (depends: 37) [deep]
├── Task 41: 3-tier memory system (working/short/long-term) (depends: 31) [deep]
├── Task 42: User state machine (daily/project/explore modes) (depends: 31) [deep]
├── Task 43: Auto weekly report generation (depends: 28,33) [unspecified-high]
└── Task 44: Advanced feedback skill system (depends: 15,37) [deep]

Wave 3.2 (After 3.1 — clustering + integration):
├── Task 45: Leiden community detection for concepts (depends: 27,31) [deep]
├── Task 46: Report UI page + PDF export (depends: 43,30) [visual-engineering]
├── Task 47: Cognitive dashboard - learning progress (depends: 40,41,30) [visual-engineering]
└── Task 48: Phase 3 integration tests (depends: 40-47) [deep]

=== PHASE 4: Full Vision ===

Wave 4.1 (After Phase 3 — connectors + exploration):
├── Task 49: Connector framework + 5 new connectors batch 1 (depends: 7) [unspecified-high]
├── Task 50: Connector batch 2 - 5 more connectors (depends: 49) [unspecified-high]
├── Task 51: ε-greedy exploration mechanism (depends: 20,32) [deep]
├── Task 52: "Explain concept" QA dialog flow (depends: 33,14) [deep]
└── Task 53: Knowledge graph interactive visualization (depends: 31,30) [visual-engineering]

Wave 4.2 (After 4.1 — polish + export):
├── Task 54: Content export - Markdown + PDF (depends: 35) [unspecified-high]
├── Task 55: Admin panel + analytics dashboard (depends: 30) [visual-engineering]
├── Task 56: Performance optimization + caching (depends: all) [deep]
├── Task 57: Spaced repetition reminders in Telegram (depends: 40,14) [quick]
└── Task 58: Phase 4 integration tests + full E2E (depends: 49-57) [deep]

Wave FINAL (After ALL tasks — independent review, 4 parallel):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Agent-executed QA sweep (unspecified-high)
└── Task F4: Scope fidelity check (deep)

Critical Path: T1 → T2 → T7 → T9 → T13 → T17 → T19 → T20 → T24 → T27 → T28 → T32 → T40 → T51
Parallel Speedup: ~65% faster than sequential (estimated)
Max Concurrent: 6 (Waves 0.1, 0.2)
```

### Dependency Matrix

> Note: This table is a high-level snapshot. For execution order, use each task's `**Blocked By**` and `**Blocks**` as the source of truth.

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1 | — | Tasks 2, 3, 4, 5, 6 | 0.1 |
| 2 | Task 1 | Tasks 7, 8, 12, 14 | 0.1 |
| 3 | Task 1 | Tasks 7-12 | 0.1 |
| 4 | Task 1 | Tasks 9, 10, 11 | 0.1 |
| 5 | Task 1 | Tasks 9, 10, 11 | 0.1 |
| 6 | Task 1 | Tasks 13, 16 | 0.1 |
| 7 | Tasks 2, 3 | Tasks 13, 16, 49 | 0.2 |
| 8 | Tasks 2, 3 | Tasks 13, 16 | 0.2 |
| 9 | Tasks 3, 4, 5 | Task 13 | 0.2 |
| 10 | Tasks 3, 4, 5 | Task 13, 28 | 0.2 |
| 11 | Tasks 3, 4, 5 | Task 13, 19 | 0.2 |
| 12 | Tasks 2, 3 | Tasks 13, 14, 20-22 | 0.2 |
| 13 | Tasks 6, 9, 10, 11, 12 | Tasks 17, 20, 24 | 0.3 |
| 14 | Tasks 1, 3, 6 | Tasks 16, 23, 57 | 0.3 |
| 15 | Tasks 1, 6, 12 | Tasks 17, 24 | 0.3 |
| 16 | Tasks 12, 14, 15 | Tasks 20, 23, 24 | 0.3 |
| 17 | Tasks 13, 14, 15, 16 | Tasks 19-26 (Phase 1) | 0.4 |
| 18 | — | — | 0.4 |
| 19 | Tasks 11, 17 | Tasks 20, 32 | 1.1 |
| 20 | Tasks 11, 16, 17 | Tasks 24, 32, 51 | 1.1 |
| 21 | Tasks 12, 17 | Tasks 25, 33 | 1.1 |
| 22 | Tasks 12, 17 | Task 26 | 1.1 |
| 23 | Tasks 14, 16, 19 | Task 26 | 1.1 |
| 24 | Tasks 15, 16, 20 | Task 26, 42 | 1.2 |
| 25 | Tasks 21, 22 | Task 26 | 1.2 |
| 26 | Tasks 19-25 | Phase 2 tasks (T27+) | 1.2 |
| 27 | Tasks 17, 26 (Phase 1 complete) | Tasks 28, 31, 32, 33, 37, 45 | 2.1 |
| 28 | Tasks 27, 4 (LLM client), 10 (understanding output) | Tasks 32, 33, 37 | 2.1 |
| 29 | Tasks 26 (Phase 1 complete) | Tasks 30, 34, 35, 36 | 2.1 |
| 30 | Task 29 | Tasks 34, 35, 36 | 2.1 |
| 31 | Task 27 | Tasks 32, 37, 40, 42, 45 | 2.1 |
| 32 | Tasks 27, 28, 31, 19 | Tasks 38, 42, 51 | 2.2 |
| 33 | Tasks 27 (Neo4j schema), 21 (Meilisearch), 13 (content processing pipeline) | Tasks 37, 38 (KG update needs query engine; integration tests need all components) | 2.2 |
| 34 | Tasks 29 (Next.js scaffolding), 30 (layout shell) | Task 39 (frontend tests) | 2.2 |
| 35 | Tasks 29 (Next.js scaffolding), 30 (layout shell), 10 (AI analysis generation) | Task 39 (frontend tests) | 2.2 |
| 36 | Task 30, Task 15, Task 24 | Task 39 | 2.2 |
| 37 | Tasks 24, 33, 28 | Task 38 | 2.2 |
| 38 | Tasks 33-37 | — | 2.3 |
| 39 | Tasks 34, 35, 36 | — | 2.3 |
| 40 | Task 2 (DB schema/models), Task 15 (Celery Beat scheduling) | Task 48 (Phase 3 tests), Task 57 (Telegram reminders) | 3.1 |
| 41 | Task 2 (DB schema/models), Task 20 (push ranker uses memory context) | Task 48 | 3.1 |
| 42 | Task 14 (Telegram bot commands), Task 20 (push ranker) | Task 48 | 3.1 |
| 43 | Tasks 37 (KG updates provide data), 40 (FSRS provides review stats), 41 (memory provides context) | Task 48 | 3.1 |
| 44 | Task 37 (KGUpdater to refactor) | Task 48 | 3.1 |
| 45 | Task 27 (Neo4j schema), Task 37 (KG has data) | Task 48 | 3.2 |
| 46 | Task 43 (reports must exist), Task 29 (Next.js foundation) | Task 48 | 3.2 |
| 47 | Tasks 40 (FSRS data), 41 (memory data), 45 (community data), 26 (Next.js) | Task 48 | 3.2 |
| 48 | Tasks 40-47 | — | 3.2 |
| 49 | Task 7 (existing connector base), Task 13 (Phase 0 pipeline), Task 27 (Neo4j integration) | Task 50 (needs framework v2), Task 55 (admin panel needs connector list), Task 58 (final E2E) | 4.1 |
| 50 | Task 49 (connector framework v2 must exist first) | Task 55 (admin panel), Task 58 (final E2E) | 4.1 |
| 51 | Task 20 (push ranker), Task 27 (Neo4j KG for graph traversal), Task 45 (community detection for cross-domain identification) | Task 55 (admin panel shows exploration stats), Task 58 (final E2E) | 4.1 |
| 52 | Task 14 (Telegram feedback handler), Task 27 (KG service for concept lookup), Task 28 (content subgraph for concept extraction) | Task 55 (admin shows dialog stats), Task 58 (final E2E) | 4.1 |
| 53 | Task 30 (Next.js dashboard shell), Task 27 (Neo4j KG service), Task 45 (community detection) | Task 58 (final E2E) | 4.1 |
| 54 | Task 30 (dashboard shell for frontend buttons), Task 43 (report generation for report export), Task 28 (content subgraph for mermaid diagrams) | Task 58 (final E2E) | 4.2 |
| 55 | Task 30 (dashboard shell), Task 49 (connector list API), Task 13 (pipeline for monitoring), Task 20 (ranker for match audit) | Task 58 (final E2E) | 4.2 |
| 56 | ALL Phase 1-3 and Wave 4.1-4.2 tasks (optimize what exists) | Task 58 (final E2E should test optimized system) | 4.2 |
| 57 | Task 40 (FSRS implementation), Task 14 (Telegram bot feedback handlers), Task 24 (push schedule/time windows) | Task 58 (final E2E includes review flow) | 4.2 |
| 58 | ALL Tasks 49-57 | Final Verification Wave | 4.2 |
### Agent Dispatch Summary

- **0.1**: **6 tasks** — T1-T6 → `quick`
- **0.2**: **6 tasks** — T7,T8 → `deep`, T9,T10 → `deep`, T11 → `quick`, T12 → `unspecified-high`
- **0.3**: **4 tasks** — T13 → `deep`, T14 → `unspecified-high`, T15 → `quick`, T16 → `quick`
- **0.4**: **2 tasks** — T17 → `deep`, T18 → `writing`
- **1.1**: **5 tasks** — T19,T20 → `deep`, T21,T22 → `unspecified-high`, T23 → `quick`
- **1.2**: **3 tasks** — T24 → `deep`, T25 → `quick`, T26 → `deep`
- **2.1**: **5 tasks** — T27 → `unspecified-high`, T28,T31 → `deep`, T29 → `quick`, T30 → `visual-engineering`
- **2.2**: **6 tasks** — T32 → `ultrabrain`, T33,T37 → `deep`, T34-T36 → `visual-engineering`
- **2.3**: **2 tasks** — T38 → `deep`, T39 → `unspecified-high`
- **3.1**: **5 tasks** — T40-T42,T44 → `deep`, T43 → `unspecified-high`
- **3.2**: **4 tasks** — T45,T48 → `deep`, T46,T47 → `visual-engineering`
- **4.1**: **5 tasks** — T49,T50 → `unspecified-high`, T51,T52 → `deep`, T53 → `visual-engineering`
- **4.2**: **5 tasks** — T54 → `unspecified-high`, T55 → `visual-engineering`, T56,T58 → `deep`, T57 → `quick`
- **FINAL**: **4 tasks** — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info + QA Scenarios.
> **A task WITHOUT QA Scenarios is INCOMPLETE. No exceptions.**

<!-- TASKS_START -->
### Phase 0 — MVP Foundation

#### Wave 0.1 — Infrastructure + Scaffolding

- [ ] 1. Project Scaffolding + Docker Compose + Dev Tooling

  **What to do**:
  - Create Python project with `pyproject.toml` (dependencies: fastapi, uvicorn, celery, redis, sqlalchemy[asyncio], asyncpg, psycopg2-binary, alembic, pydantic-settings, structlog, httpx, jinja2, trafilatura, feedparser, arxiv, aiogram, openai, ollama)
  - Initialize Python environment management with `uv` (`uv sync`, `uv add ...`, `uv run ...`)
  - Create `docker-compose.yml` with 6 services: `api` (FastAPI:8000), `bot` (aiogram:8081), `worker` (Celery), `scheduler` (Celery Beat), `postgres` (5432), `redis` (6379, appendonly=yes)
  - Create `docker-compose.test.yml` for integration tests (separate DB)
  - Create `Dockerfile` with multi-stage build (builder + runtime)
  - Create `Makefile` with targets: `up`, `down`, `test`, `lint`, `migrate`, `logs`, `shell` (Python targets call `uv run ...`)
  - Create `.env.example` with all config vars (DB URLs, API keys, Ollama host)
  - Create `src/` package structure: `src/__init__.py`, `src/main.py` (FastAPI app factory), `src/config.py` (Pydantic Settings)
  - Set up `structlog` with JSON output in `src/logging.py`
  - Set up `ruff` for linting + formatting in `pyproject.toml`
  - Set up `mypy` for type checking in `pyproject.toml`
  - Create `tests/` directory structure: `tests/unit/`, `tests/integration/`, `tests/fixtures/`, `tests/conftest.py`
  - Write initial test: `tests/unit/test_config.py` — verify config loads from env
  - TDD: Write test first (config loads correctly), then implement config

  **Must NOT do**:
  - Do NOT install or configure Neo4j, Meilisearch, or Next.js
  - Do NOT create abstract factory patterns or plugin systems
  - Do NOT add CI/CD pipelines yet
  - Do NOT include Ollama in Docker Compose (runs on host)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Pure scaffolding, no complex logic — file creation and configuration
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 0.1 (foundation — must complete first)
  - **Blocks**: Tasks 2, 3, 4, 5, 6
  - **Blocked By**: None (first task)

  **References**:

  **Pattern References**:
  - `DESIGN.md:1117-1145` — Tech stack reference table (use for dependency versions)
  - `DESIGN.md:1074-1115` — MVP Phase 0 roadmap (scope boundaries)

  **External References**:
  - FastAPI project structure: https://fastapi.tiangolo.com/tutorial/bigger-applications/
  - structlog setup: https://www.structlog.org/en/stable/getting-started.html
  - Pydantic Settings: https://docs.pydantic.dev/latest/concepts/pydantic_settings/

  **WHY Each Reference Matters**:
  - DESIGN.md tech stack table lists exact versions and alternatives — use to pin dependency versions
  - DESIGN.md Phase 0 roadmap defines what's in scope — prevents over-building in scaffolding

  **Acceptance Criteria**:

  **TDD:**
  - [ ] Test file created: `tests/unit/test_config.py`
  - [ ] `uv run pytest tests/unit/test_config.py -v` → PASS

  **QA Scenarios:**

  ```
  Scenario: Docker Compose starts all services healthy
    Tool: Bash
    Preconditions: Docker daemon running, .env file with test values
    Steps:
      1. Run `docker compose up -d --build`
      2. Wait 15 seconds for startup
      3. Run `docker compose ps --format json`
      4. Assert all 6 services show status 'running'
      5. Run `curl -sf http://localhost:8000/health`
      6. Assert response: {"status": "ok"}
    Expected Result: All 6 services running, health endpoint returns ok
    Failure Indicators: Any service in 'exited' state, health endpoint 404/500
    Evidence: .sisyphus/evidence/task-1-docker-healthy.txt

  Scenario: Development tooling works
    Tool: Bash
    Preconditions: Project scaffolded
    Steps:
      1. Run `make lint` — assert ruff exits 0
      2. Run `make test` — assert `uv run pytest` discovers tests and exits 0
      3. Verify config loads: `uv run python -c "from src.config import settings; print(settings.DATABASE_URL)"`
    Expected Result: All dev tools functional
    Failure Indicators: Import errors, missing dependencies
    Evidence: .sisyphus/evidence/task-1-dev-tooling.txt
  ```

  **Commit**: YES
  - Message: `chore(infra): scaffold project + Docker Compose + dev tooling`
  - Files: `docker-compose.yml`, `Dockerfile`, `pyproject.toml`, `Makefile`, `.env.example`, `src/`, `tests/`
  - Pre-commit: `uv run ruff check . && uv run pytest tests/unit/test_config.py -v`

- [ ] 2. PostgreSQL Schema + Alembic Migrations

  **What to do**:
  - Set up Alembic in `alembic/` with `alembic.ini` and `env.py` (async engine support)
  - Define SQLAlchemy models in `src/models/`:
    - `src/models/base.py`: Base class with id, created_at, updated_at, user_id FK
    - `src/models/content.py`: `Content` table — source, source_url, source_id, title, raw_text, extracted_text, author, published_at, fetched_at, language, metadata (JSONB), pipeline_status (enum: fetched/gatekept/understood/scored/indexed/failed), pipeline_error, quality_score, summary, key_points (JSONB), domains (JSONB), estimated_read_time
    - `src/models/source.py`: `Source` table — type (enum: rss/arxiv), name, url, config (JSONB), is_active, last_fetched_at, fetch_interval_minutes
    - `src/models/feedback.py`: `Feedback` table — content_id FK, user_id FK, type (enum: valuable_learned/save_for_later/not_valuable/already_known), created_at
    - `src/models/user.py`: `User` table — telegram_chat_id, preferences (JSONB), created_at
  - Create initial Alembic migration
  - Create `src/db.py` with async engine + session factory (asyncpg for FastAPI, psycopg2 for Celery)
  - TDD: Write model tests first, then implement

  **Must NOT do**:
  - Do NOT add Neo4j or graph-related columns
  - Do NOT create overly complex relationships — keep flat for Phase 0
  - Do NOT add Meilisearch sync triggers

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Standard ORM schema definition
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T3-T6, after T1)
  - **Parallel Group**: Wave 0.1
  - **Blocks**: Tasks 7, 8, 12, 14
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `DESIGN.md:128-141` — RawContent interface (maps to Content model fields)
  - `DESIGN.md:207-230` — ContentUnderstanding interface (Phase 0 subset)
  - `Folo/packages/internal/database/src/schemas/index.ts` — Folo Drizzle schema reference

  **WHY Each Reference Matters**:
  - RawContent defines the data contract — DB must store all these fields
  - Folo schema shows mature feeds/entries pattern — structural reference

  **Acceptance Criteria**:

  **TDD:**
  - [ ] Test file created: `tests/unit/test_models.py`
  - [ ] `uv run pytest tests/unit/test_models.py -v` → PASS

  **QA Scenarios:**

  ```
  Scenario: Alembic migration applies cleanly
    Tool: Bash
    Preconditions: PostgreSQL running in Docker
    Steps:
      1. Run `alembic upgrade head`
      2. Run `docker compose exec postgres psql -U alice -d alice -c "\\dt"`
      3. Assert tables exist: content, source, feedback, users
      4. Run `alembic downgrade base` then `alembic upgrade head` — assert idempotent
    Expected Result: All tables created, migration reversible
    Failure Indicators: alembic errors, missing tables
    Evidence: .sisyphus/evidence/task-2-alembic.txt

  Scenario: Pipeline status enum works
    Tool: Bash
    Preconditions: Migration applied
    Steps:
      1. Insert content with pipeline_status='fetched' — succeeds
      2. Update to 'gatekept' — succeeds
      3. Attempt 'invalid_value' — assert constraint violation
    Expected Result: Valid transitions work, invalid rejected
    Evidence: .sisyphus/evidence/task-2-enum.txt
  ```

  **Commit**: YES
  - Message: `feat(db): PostgreSQL schema + Alembic migrations`
  - Files: `alembic/`, `src/models/`, `src/db.py`
  - Pre-commit: `uv run pytest tests/unit/test_models.py -v`

- [ ] 3. Pydantic Models + Shared Types
  **What to do**:
  - Create `src/schemas/` package with Pydantic v2 models:
    - `src/schemas/content.py`: `RawContentSchema`, `ContentResponseSchema`, `ContentUnderstandingSchema` (Phase 0: summary, key_points, domains, estimated_read_time)
    - `src/schemas/source.py`: `SourceConfigSchema`, `FetchResultSchema`
    - `src/schemas/feedback.py`: `FeedbackCreateSchema`, `FeedbackType` enum
    - `src/schemas/pipeline.py`: `PipelineStatus` enum, `PipelineTaskSchema`
    - `src/schemas/gatekeeper.py`: `GatekeeperDecision` (pass/reject + reason + confidence)
    - `src/schemas/quality.py`: `QualityScoreSchema` (single 1-10 score + reason)
  - TDD: Write schema validation tests first

  **Must NOT do**:
  - Do NOT include ContentSubgraph schema (Phase 2)
  - Do NOT include 7-dimension quality scoring (Phase 1)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Pure data model definitions
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T2, T4, T5, T6)
  - **Parallel Group**: Wave 0.1
  - **Blocks**: Tasks 7-12
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `DESIGN.md:128-141` — RawContent interface → convert to Pydantic
  - `DESIGN.md:207-230` — ContentUnderstanding → Phase 0 subset

  **Acceptance Criteria**:

  **TDD:**
  - [ ] Test file: `tests/unit/test_schemas.py`
  - [ ] `uv run pytest tests/unit/test_schemas.py -v` → PASS

  **QA Scenarios:**

  ```
  Scenario: Schema validation rejects invalid data
    Tool: Bash
    Steps:
      1. Test RawContentSchema with invalid source type → ValidationError
      2. Test QualityScoreSchema with score=15 → ValidationError (1-10 range)
      3. Test FeedbackType with nonexistent type → ValueError
    Expected Result: All invalid inputs raise errors
    Evidence: .sisyphus/evidence/task-3-schema-validation.txt
  ```

  **Commit**: YES (groups with T4, T5)
  - Message: `feat(core): Pydantic schemas + shared types`
  - Files: `src/schemas/`
  - Pre-commit: `uv run pytest tests/unit/test_schemas.py -v`
- [ ] 4. LLM Abstraction Layer (LLMClient Protocol + Mock)
  **What to do**:
  - Create `src/llm/` package:
    - `src/llm/protocol.py`: `LLMClient` Protocol — `async def complete(prompt, system, temperature, max_tokens, response_format) -> str`, `async def complete_structured(prompt, system, response_model: type[T]) -> T`
    - `src/llm/deepseek.py`: `DeepSeekClient` — uses `openai` SDK with `base_url="https://api.deepseek.com"`, retry with exponential backoff (3 retries, 600s timeout)
    - `src/llm/ollama.py`: `OllamaClient` — connects to configurable OLLAMA_HOST (default: `host.docker.internal:11434`), timeout handling
    - `src/llm/mock.py`: `MockLLMClient` — returns fixture data from `tests/fixtures/llm_responses/`
    - `src/llm/factory.py`: `create_llm_client(provider) -> LLMClient`
  - Create fixtures: `tests/fixtures/llm_responses/gatekeeper_pass.json`, `gatekeeper_reject.json`, `understanding_response.json`, `quality_score.json`
  - TDD: Write protocol conformance tests first

  **Must NOT do**:
  - Do NOT implement LangChain (keep raw OpenAI SDK)
  - Do NOT add streaming or caching

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Well-defined protocol pattern
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T2, T3, T5, T6)
  - **Parallel Group**: Wave 0.1
  - **Blocks**: Tasks 9, 10, 11
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `DESIGN.md:186-205` — Gatekeeper LLM calls
  - `DESIGN.md:207-230` — Understanding LLM calls

  **External References**:
  - DeepSeek API (OpenAI-compatible): https://platform.deepseek.com/api-docs
  - Ollama Python: https://github.com/ollama/ollama-python

  **Acceptance Criteria**:

  **TDD:**
  - [ ] Test file: `tests/unit/test_llm.py`
  - [ ] `uv run pytest tests/unit/test_llm.py -v` → PASS

  **QA Scenarios:**

  ```
  Scenario: Mock client returns fixture data
    Tool: Bash
    Steps:
      1. Run pytest test for mock client fixture loading
      2. Assert structured output parses into Pydantic model
    Expected Result: Mock client fully functional
    Evidence: .sisyphus/evidence/task-4-mock-client.txt
  Scenario: DeepSeek error handling
    Tool: Bash
    Steps:
      1. Test retry logic on mocked timeout
      2. Assert retries with backoff, raises after max
    Expected Result: Clean error handling with retry
    Evidence: .sisyphus/evidence/task-4-error-handling.txt
  ```

  **Commit**: YES (groups with T3, T5)
  - Message: `feat(core): LLM abstraction layer + mock client + fixtures`
  - Files: `src/llm/`, `tests/fixtures/llm_responses/`
  - Pre-commit: `uv run pytest tests/unit/test_llm.py -v`
- [ ] 5. Prompt Templates Directory + Jinja2 Setup
  **What to do**:
  - Create `prompts/` directory with Jinja2 templates:
    - `prompts/gatekeeper.j2` — Binary pass/reject based on quality criteria
    - `prompts/understanding.j2` — Extract summary, key_points, domains, read_time
    - `prompts/quality_score.j2` — Rate 1-10 with reasoning
    - `prompts/push_reason.j2` — Generate personalized push reason
  - Create `src/prompts.py`: `PromptManager` — loads templates, renders with variables
  - All prompts include JSON output format, bilingual handling (Chinese/English)
  - TDD: Write prompt rendering tests first

  **Must NOT do**:
  - Do NOT create prompt engineering framework
  - Do NOT add Phase 1+ prompts (subgraph, KG, reports)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Template files + simple loader
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T2, T3, T4, T6)
  - **Parallel Group**: Wave 0.1
  - **Blocks**: Tasks 9, 10, 11
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `DESIGN.md:186-205` — Gatekeeper criteria for prompt content
  - `DESIGN.md:207-230` — Understanding fields for extraction prompt
  - `DESIGN.md:399-432` — Quality scoring for scoring prompt guidance

  **Acceptance Criteria**:

  **TDD:**
  - [ ] Test file: `tests/unit/test_prompts.py`
  - [ ] `uv run pytest tests/unit/test_prompts.py -v` → PASS

  **QA Scenarios:**

  ```
  Scenario: All templates render without errors
    Tool: Bash
    Steps:
      1. Run pytest for all template rendering
      2. Assert each renders with sample variables
      3. Assert rendered output contains JSON format instructions
    Expected Result: All 4 templates render correctly
    Evidence: .sisyphus/evidence/task-5-templates.txt
  ```
  **Commit**: YES (groups with T3, T4)
  - Message: `feat(core): prompt templates + Jinja2 manager`
  - Files: `prompts/`, `src/prompts.py`
  - Pre-commit: `uv run pytest tests/unit/test_prompts.py -v`
- [ ] 6. Celery + Redis Worker Infrastructure
  **What to do**:
  - Create `src/worker/` package:
    - `src/worker/celery_app.py`: Celery app factory with Redis broker, task routes
    - `src/worker/tasks.py`: Placeholder stubs for pipeline stages (fetch, gate, understand, score, index) — each reads DB, processes, writes DB, updates pipeline_status
    - `src/worker/scheduler.py`: Celery Beat schedule (fetch every 30 min)
  - Configure Redis `appendonly yes` in Docker Compose
  - Configure Celery: `autoretry_for=(Exception,)`, `retry_backoff=True`, `max_retries=5`, `time_limit=600`
  - Separate connection pool for workers (psycopg2 sync)
  - TDD: Write task execution tests with mocked deps

  **Must NOT do**:
  - Do NOT use Celery chains — individual tasks with DB state
  - Do NOT implement complex routing or Flower

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Standard Celery setup
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T2-T5)
  - **Parallel Group**: Wave 0.1
  - **Blocks**: Tasks 13, 16
  - **Blocked By**: Task 1

  **References**:

  **External References**:
  - Celery docs: https://docs.celeryq.dev/en/stable/
  - Redis AOF: https://redis.io/docs/management/persistence/

  **Pattern References**:
  - `DESIGN.md:1135-1136` — Celery + Redis confirmed

  **Acceptance Criteria**:

  **TDD:**
  - [ ] Test file: `tests/unit/test_worker.py`
  - [ ] `uv run pytest tests/unit/test_worker.py -v` → PASS

  **QA Scenarios:**

  ```
  Scenario: Worker starts and discovers tasks
    Tool: Bash
    Preconditions: Docker Compose running
    Steps:
      1. Run `docker compose logs worker --tail=20`
      2. Assert log contains 'celery@worker ready'
      3. Assert registered tasks include pipeline stages
    Expected Result: Worker running with all tasks registered
    Evidence: .sisyphus/evidence/task-6-worker.txt
  Scenario: Redis persistence configured
    Tool: Bash
    Steps:
      1. `docker compose exec redis redis-cli CONFIG GET appendonly`
      2. Assert 'yes'
    Expected Result: AOF enabled
    Evidence: .sisyphus/evidence/task-6-redis.txt
  ```
  **Commit**: YES
  - Message: `feat(worker): Celery + Redis infrastructure + task stubs`
  - Files: `src/worker/`
  - Pre-commit: `uv run pytest tests/unit/test_worker.py -v`
#### Wave 0.2 — Connectors + Gatekeeper (MAX PARALLEL after Wave 0.1)

- [ ] 7. RSS/Atom Connector with Full-Text Extraction
  **What to do**:
  - Create `src/connectors/base.py`: `BaseConnector` ABC with `async def fetch(config: SourceConfigSchema) -> list[RawContentSchema]`
  - Create `src/connectors/rss.py`: `RSSConnector(BaseConnector)`:
    - Uses `feedparser` to parse RSS/Atom feeds
    - Uses `trafilatura` to extract full article text from each entry URL
    - Falls back to RSS summary if trafilatura extraction fails (paywall, JS-only page, dead link)
    - Sets `extraction_failed` flag when full-text not available
    - Normalizes dates to UTC, handles missing fields gracefully
    - Content dedup via URL normalization (strip tracking params, normalize www/non-www)
  - Create `tests/fixtures/rss_feeds/`: sample RSS XML files (HN, arXiv RSS, tech blog)
  - Create `src/connectors/rss.py` FastAPI endpoint: `POST /api/v1/connectors/rss/fetch`

  - TDD: Write connector tests with fixture XML first, then implement
  **Must NOT do**:
  - Do NOT build a connector plugin registry or dynamic loading
  - Do NOT implement RSS feed discovery/OPML import
  - Do NOT add webhook/pubsubhubbub support
  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Full-text extraction with trafilatura has edge cases (paywalls, encodings, timeouts)
  - **Skills**: []
  **Parallelization**:
  - **Can Run In Parallel**: YES (with T8-T12)
  - **Parallel Group**: Wave 0.2
  - **Blocks**: Tasks 13, 16, 49
  - **Blocked By**: Tasks 2, 3
  **References**:
  **Pattern References**:
  - `DESIGN.md:128-141` — RawContent interface (connector output contract)
  - `DESIGN.md:143-163` — Connector layer design and SourceType enum
  - `Folo/packages/readability/src/index.ts` — Folo's content extraction pattern (Mozilla Readability + DOMPurify)
  **External References**:
  - feedparser docs: https://feedparser.readthedocs.io/
  - trafilatura docs: https://trafilatura.readthedocs.io/
  **WHY Each Reference Matters**:
  - DESIGN.md RawContent is the output contract — connector must produce exactly these fields
  - DESIGN.md connector layer shows intended architecture — follow minimal ABC pattern
  - Folo readability package shows extraction+cleanup pattern — trafilatura serves same purpose in Python
  **Acceptance Criteria**:
  **TDD:**
  - [ ] Test file: `tests/unit/test_rss_connector.py`
  - [ ] `uv run pytest tests/unit/test_rss_connector.py -v` → PASS (parse fixture XML, extract fields, handle errors)
  **QA Scenarios:**
  ```
  Scenario: RSS connector fetches real HN feed
    Tool: Bash
    Preconditions: API running, internet access
    Steps:
      1. curl -sf http://localhost:8000/api/v1/connectors/rss/fetch -H "Content-Type: application/json" -d '{"feed_url": "https://hnrss.org/frontpage", "limit": 3}'
      2. Assert response has "items" array with length >= 1
      3. Assert each item has: source_url, title, raw_text (non-empty), fetched_at
      4. Assert at least one item has extracted_text (full article via trafilatura)
    Expected Result: Real RSS content fetched and parsed
    Failure Indicators: Empty items, missing fields, trafilatura timeout
    Evidence: .sisyphus/evidence/task-7-rss-real-fetch.json

  Scenario: RSS connector handles extraction failure gracefully
    Tool: Bash
    Steps:
      1. Run pytest test with fixture RSS pointing to nonexistent URLs
      2. Assert extraction_failed=True for those entries
      3. Assert raw_text falls back to RSS summary
      4. Assert no exceptions raised — graceful degradation
    Expected Result: Failed extractions logged, RSS summary used as fallback
    Evidence: .sisyphus/evidence/task-7-rss-fallback.txt
  ```
  **Commit**: YES
  - Message: `feat(connectors): RSS/Atom connector with trafilatura full-text extraction`
  - Files: `src/connectors/`, `tests/fixtures/rss_feeds/`
  - Pre-commit: `uv run pytest tests/unit/test_rss_connector.py -v`

- [ ] 8. arXiv Connector
  **What to do**:
  - Create `src/connectors/arxiv.py`: `ArxivConnector(BaseConnector)`:
    - Uses `arxiv` Python package to search by category (cs.AI, cs.LG, etc.) or keyword
    - Extracts: title, abstract, authors, published date, PDF URL, categories
    - Maps to `RawContentSchema` (abstract as raw_text, PDF URL in metadata)
    - Respects arXiv API rate limits (3 second delay between requests)
    - Configurable: categories, max_results, date range
  - Create `tests/fixtures/arxiv_responses/`: sample API response JSON
  - Create FastAPI endpoint: `POST /api/v1/connectors/arxiv/fetch`
  - TDD: Write tests with mocked arxiv responses first
  **Must NOT do**:
  - Do NOT download/parse PDF files (use abstract only for Phase 0)
  - Do NOT implement citation graph analysis
  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: arXiv API has quirks (rate limiting, date formatting, category taxonomy)
  - **Skills**: []
  **Parallelization**:
  - **Can Run In Parallel**: YES (with T7, T9-T12)
  - **Parallel Group**: Wave 0.2
  - **Blocks**: Tasks 13, 16
  - **Blocked By**: Tasks 2, 3
  **References**:
  **Pattern References**:
  - `DESIGN.md:143-163` — Connector design, arXiv as a source type
  - `DESIGN.md:128-141` — RawContent output contract
  **External References**:
  - arxiv Python package: https://github.com/lukasschwab/arxiv.py
  **Acceptance Criteria**:
  **TDD:**
  - [ ] Test file: `tests/unit/test_arxiv_connector.py`
  - [ ] `uv run pytest tests/unit/test_arxiv_connector.py -v` → PASS
  **QA Scenarios:**
  ```
  Scenario: arXiv connector fetches real papers
    Tool: Bash
    Steps:
      1. curl -sf http://localhost:8000/api/v1/connectors/arxiv/fetch -H "Content-Type: application/json" -d '{"query": "cat:cs.AI", "max_results": 3}'
      2. Assert response has "items" array with length == 3
      3. Assert each item has: title, raw_text (abstract), source_url (arxiv link), author, published_at
    Expected Result: 3 arXiv papers fetched with metadata
    Evidence: .sisyphus/evidence/task-8-arxiv-fetch.json
  Scenario: arXiv connector respects rate limits
    Tool: Bash
    Steps:
      1. Run pytest test that makes 2 consecutive requests
      2. Assert >= 3 second delay between API calls (check timing in logs)
    Expected Result: Rate limit respected
    Evidence: .sisyphus/evidence/task-8-arxiv-rate-limit.txt
  ```
  **Commit**: YES
  - Message: `feat(connectors): arXiv connector with category search`
  - Files: `src/connectors/arxiv.py`, `tests/fixtures/arxiv_responses/`
  - Pre-commit: `uv run pytest tests/unit/test_arxiv_connector.py -v`
- [ ] 9. Gatekeeper Service — Ollama + Rule-Based Fallback
  **What to do**:
  - Create `src/services/gatekeeper.py`: `GatekeeperService`:
    - Primary: Sends content to local Qwen 1.5B via OllamaClient for binary classification (pass/reject)
    - Uses `prompts/gatekeeper.j2` template with content text
    - Parses response into `GatekeeperDecision` (pass/reject + reason + confidence)
    - Fallback (when Ollama unavailable): Rule-based filter:
      - Reject if: text length < 100 chars, detected language doesn't match user preferences, duplicate URL in DB
      - Pass otherwise with confidence=0.5 and reason="rule-based fallback"
    - Health check: ping Ollama before each batch, switch to fallback if unreachable
    - Log all decisions with structlog (content_id, decision, confidence, method: ollama/rule-based)
  - TDD: Write tests for both Ollama path (mocked) and rule-based path
  **Must NOT do**:
  - Do NOT implement complex NLP-based filtering (just LLM or rules)
  - Do NOT add content fingerprinting/SimHash (that's Task 22)
  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Dual-path logic (LLM + fallback) with health checking requires careful design
  - **Skills**: []
  **Parallelization**:
  - **Can Run In Parallel**: YES (with T7, T8, T10-T12)
  - **Parallel Group**: Wave 0.2
  - **Blocks**: Task 13
  - **Blocked By**: Tasks 3, 4, 5
  **References**:
  **Pattern References**:
  - `DESIGN.md:186-205` — Gatekeeper design with criteria (substance, evidence, logic, not clickbait)
  - `src/llm/ollama.py` (from Task 4) — OllamaClient for LLM calls
  - `src/schemas/gatekeeper.py` (from Task 3) — GatekeeperDecision schema
  **WHY Each Reference Matters**:
  - DESIGN.md gatekeeper section defines the exact quality criteria — prompt must encode these
  - OllamaClient is the interface — gatekeeper consumes it, doesn't create its own HTTP calls
  **Acceptance Criteria**:
  **TDD:**
  - [ ] Test file: `tests/unit/test_gatekeeper.py`
  - [ ] `uv run pytest tests/unit/test_gatekeeper.py -v` → PASS (mock Ollama pass, mock Ollama reject, fallback path)
  **QA Scenarios:**
  ```
  Scenario: Gatekeeper passes quality content via mock LLM
    Tool: Bash
    Steps:
      1. Run pytest with MockLLMClient returning pass decision
      2. Assert GatekeeperDecision.passed == True
      3. Assert decision has reason and confidence > 0.7
    Expected Result: Quality content passes gatekeeper
    Evidence: .sisyphus/evidence/task-9-gatekeeper-pass.txt
  Scenario: Gatekeeper falls back to rules when Ollama unavailable
    Tool: Bash
    Steps:
      1. Run pytest with OllamaClient configured to unreachable host
      2. Send content with text > 100 chars
      3. Assert falls back to rule-based: passed=True, confidence=0.5, reason contains "rule-based"
      4. Send content with text < 100 chars
      5. Assert rule-based rejects: passed=False
    Expected Result: Graceful fallback to rules
    Evidence: .sisyphus/evidence/task-9-gatekeeper-fallback.txt
  ```
  **Commit**: YES
  - Message: `feat(services): gatekeeper with Ollama + rule-based fallback`
  - Files: `src/services/gatekeeper.py`
  - Pre-commit: `uv run pytest tests/unit/test_gatekeeper.py -v`
- [ ] 10. Content Understanding Service — DeepSeek
  **What to do**:
  - Create `src/services/understanding.py`: `UnderstandingService`:
    - Takes gatekept content, sends to DeepSeek via `DeepSeekClient.complete_structured()`
    - Uses `prompts/understanding.j2` template
    - Extracts `ContentUnderstandingSchema` (Phase 0: summary, key_points, domains, estimated_read_time)
    - Structured output: Pydantic model validation on LLM response
    - Handles bilingual content (Chinese/English) — prompt instructs LLM to output in content's language
    - Retry on malformed JSON (re-prompt with "Please output valid JSON")
    - Stores result in Content DB row (summary, key_points, domains, estimated_read_time columns)
  - TDD: Write tests with fixture DeepSeek responses first
  **Must NOT do**:
  - Do NOT extract concepts, prerequisites, or content subgraph (Phase 2)
  - Do NOT implement content categorization beyond simple domains list
  - Do NOT add streaming
  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: LLM structured output parsing with retry logic, bilingual handling
  - **Skills**: []
  **Parallelization**:
  - **Can Run In Parallel**: YES (with T7-T9, T11, T12)
  - **Parallel Group**: Wave 0.2
  - **Blocks**: Task 13, 28
  - **Blocked By**: Tasks 3, 4, 5
  **References**:
  **Pattern References**:
  - `DESIGN.md:207-230` — ContentUnderstanding interface (Phase 0 uses 4 of 14 fields)
  - `src/llm/deepseek.py` (Task 4) — DeepSeekClient for API calls
  - `src/schemas/content.py` (Task 3) — ContentUnderstandingSchema
  **Acceptance Criteria**:
  **TDD:**
  - [ ] Test file: `tests/unit/test_understanding.py`
  - [ ] `uv run pytest tests/unit/test_understanding.py -v` → PASS
  **QA Scenarios:**
  ```
  Scenario: Understanding extracts structured data from content
    Tool: Bash
    Steps:
      1. Run pytest with MockLLMClient returning fixture understanding JSON
      2. Assert ContentUnderstandingSchema parsed: summary (non-empty string), key_points (list, len >= 1), domains (list), estimated_read_time (int > 0)
    Expected Result: All 4 fields extracted and validated
    Evidence: .sisyphus/evidence/task-10-understanding.txt
  Scenario: Understanding retries on malformed JSON
    Tool: Bash
    Steps:
      1. Run pytest with MockLLMClient returning invalid JSON first, valid JSON second
      2. Assert retry triggered (check call count)
      3. Assert final result is valid ContentUnderstandingSchema
    Expected Result: Automatic retry on bad JSON
    Evidence: .sisyphus/evidence/task-10-retry.txt
  ```
  **Commit**: YES
  - Message: `feat(services): content understanding via DeepSeek`
  - Files: `src/services/understanding.py`
  - Pre-commit: `uv run pytest tests/unit/test_understanding.py -v`
- [ ] 11. Quality Scoring — Simple LLM Score
  **What to do**:
  - Create `src/services/scoring.py`: `ScoringService`:
    - Takes understood content (summary + key_points available)
    - Sends to DeepSeek via `DeepSeekClient.complete_structured()` with `prompts/quality_score.j2`
    - Returns `QualityScoreSchema`: single score (1-10) + reasoning text
    - Score criteria from prompt: substance (not fluff), density (info per word), credibility (evidence-backed), novelty (not common knowledge), actionability (can be applied)
    - Threshold: score >= 6 passes to indexing, score < 6 rejected
    - Stores score and reasoning in Content DB row
  - TDD: Write tests with fixture scoring responses
  **Must NOT do**:
  - Do NOT implement 7-dimension weighted formula (Phase 1, Task 19)
  - Do NOT implement social signal scoring or timeliness scoring
  - Do NOT cache scores
  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple LLM call with single-value output — straightforward
  - **Skills**: []
  **Parallelization**:
  - **Can Run In Parallel**: YES (with T7-T10, T12)
  - **Parallel Group**: Wave 0.2
  - **Blocks**: Task 13, 19
  - **Blocked By**: Tasks 3, 4, 5
  **References**:
  **Pattern References**:
  - `DESIGN.md:399-432` — Quality scoring 7 dimensions (use as prompt guidance, not implementation)
  - `src/schemas/quality.py` (Task 3) — QualityScoreSchema
  **Acceptance Criteria**:
  **TDD:**
  - [ ] Test file: `tests/unit/test_scoring.py`
  - [ ] `uv run pytest tests/unit/test_scoring.py -v` → PASS
  **QA Scenarios:**
  ```
  Scenario: Scoring returns valid score with reasoning
    Tool: Bash
    Steps:
      1. Run pytest with MockLLMClient returning score=8 + reasoning
      2. Assert QualityScoreSchema.score is 8, reasoning is non-empty
      3. Test threshold: score=8 >= 6 → passes, score=3 < 6 → rejected
    Expected Result: Score correctly parsed and threshold applied
    Evidence: .sisyphus/evidence/task-11-scoring.txt
  ```
  **Commit**: YES
  - Message: `feat(services): simple LLM quality scoring (1-10)`
  - Files: `src/services/scoring.py`
  - Pre-commit: `uv run pytest tests/unit/test_scoring.py -v`
- [ ] 12. Content Storage + Retrieval Service
  **What to do**:
  - Create `src/services/storage.py`: `ContentStorageService`:
    - CRUD operations for Content model (create, get_by_id, list, update_pipeline_status)
    - `store_raw(raw: RawContentSchema) -> Content` — creates DB row with pipeline_status=fetched
    - `update_gatekeeper_result(content_id, decision)` — updates status to gatekept/failed
    - `update_understanding(content_id, understanding)` — updates summary, key_points, domains
    - `update_score(content_id, score)` — updates quality_score, status to scored
    - `mark_indexed(content_id)` — updates status to indexed
    - `get_pending(stage: PipelineStatus) -> list[Content]` — get content waiting for a specific stage
    - `get_pushable(min_score: float, limit: int) -> list[Content]` — get indexed content above score threshold
    - URL dedup: check `source_url` uniqueness before insert (DB unique constraint + normalize URL)
  - Create `src/services/source.py`: `SourceService` — CRUD for Source model (add/remove/list RSS feeds and arXiv configs)
  - Create FastAPI routes: `src/api/v1/content.py` and `src/api/v1/sources.py`
  - TDD: Write storage tests against real test PostgreSQL (docker-compose.test.yml)
  **Must NOT do**:
  - Do NOT implement full-text search (Meilisearch, Phase 1)
  - Do NOT implement graph queries
  - Do NOT add pagination beyond simple limit/offset
  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Multiple CRUD operations with status transitions, API routes, DB integration tests
  - **Skills**: []
  **Parallelization**:
  - **Can Run In Parallel**: YES (with T7-T11)
  - **Parallel Group**: Wave 0.2
  - **Blocks**: Tasks 13, 14, 20-22
  - **Blocked By**: Tasks 2, 3
  **References**:
  **Pattern References**:
  - `src/models/content.py` (Task 2) — Content SQLAlchemy model
  - `src/schemas/content.py` (Task 3) — Pydantic schemas for request/response
  - `Folo/packages/internal/database/src/services/` — Folo's service layer pattern (entry, feed, subscription services)
  **WHY Each Reference Matters**:
  - Content model defines DB columns — storage service wraps these with business logic
  - Folo services show a clean pattern: thin service layer over ORM with typed parameters
  **Acceptance Criteria**:
  **TDD:**
  - [ ] Test file: `tests/unit/test_storage.py`, `tests/integration/test_storage_db.py`
  - [ ] `uv run pytest tests/unit/test_storage.py -v` → PASS
  - [ ] `uv run pytest tests/integration/test_storage_db.py -v` → PASS (requires test DB)
  **QA Scenarios:**
  ```
  Scenario: Content CRUD lifecycle
    Tool: Bash
    Preconditions: API running with DB
    Steps:
      1. POST /api/v1/sources — create RSS source, assert 201
      2. POST /api/v1/connectors/rss/fetch — fetch content, assert items created
      3. GET /api/v1/content?status=fetched — assert items listed
      4. Assert each content has pipeline_status="fetched"
    Expected Result: Full create → list lifecycle works
    Evidence: .sisyphus/evidence/task-12-crud-lifecycle.json
  Scenario: URL dedup prevents duplicate content
    Tool: Bash
    Steps:
      1. Store content with source_url="https://example.com/article"
      2. Attempt to store same URL again
      3. Assert second attempt returns existing content (not duplicate)
    Expected Result: No duplicate entries for same URL
    Evidence: .sisyphus/evidence/task-12-url-dedup.txt
  ```
  **Commit**: YES
  - Message: `feat(services): content storage + retrieval + API routes`
  - Files: `src/services/storage.py`, `src/services/source.py`, `src/api/v1/`
  - Pre-commit: `uv run pytest tests/ -v`
- [ ] 13. Pipeline Orchestrator — State Machine + Celery Task Dispatch

  **What to do**:
  - Create `src/pipeline/orchestrator.py`: `PipelineOrchestrator` class:
    - Manages content lifecycle: `fetched → gatekept → understood → scored → indexed → failed`
    - State transitions stored in PostgreSQL `content.pipeline_status` column (NOT Redis)
    - Each transition dispatches the next Celery task individually (NOT chained)
    - On failure: set status to `failed` with `failure_reason` and `failed_at_stage`
    - Retry logic: max 3 retries per stage with exponential backoff (1min, 5min, 30min)
    - `process_new_content(content_id)`: entry point — validates state, dispatches gatekeeper
    - `advance_pipeline(content_id, current_stage, result)`: generic state advancer
  - Create `src/pipeline/tasks.py`: Individual Celery tasks (NOT chains):
    - `task_run_gatekeeper(content_id)` → calls GatekeeperService, advances to `gatekept`
    - `task_run_understanding(content_id)` → calls UnderstandingService, advances to `understood`
    - `task_run_scoring(content_id)` → calls ScoringService, advances to `scored`
    - `task_run_indexing(content_id)` → stores final content, advances to `indexed`
  - Create `src/pipeline/scheduler.py`: Celery Beat schedule:
    - `fetch_all_sources`: every 30 min (configurable)
    - `retry_failed`: every hour, retries failed content (< max retries)
  - TDD: Test state transitions, failure handling, retry logic

  **Must NOT do**:
  - Do NOT use Celery chains or groups — individual tasks only (Metis guardrail)
  - Do NOT store pipeline state in Redis — PostgreSQL only
  - Do NOT implement push/notification logic (Task 20)
  - Do NOT add Meilisearch indexing step (Phase 1, Task 21)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: State machine + async task orchestration requires careful edge case handling
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T14, T15)
  - **Parallel Group**: Wave 0.3
  - **Blocks**: Tasks 17, 20, 24
  - **Blocked By**: Tasks 6, 9, 10, 11, 12

  **References**:

  **Pattern References**:
  - `DESIGN.md:145-190` — Pipeline architecture (4-stage processing)
  - `src/services/gatekeeper.py` (T9), `src/services/understanding.py` (T10), `src/services/scoring.py` (T11)
  - `src/celery_app.py` (T6) — Celery app config

  **External References**:
  - Celery best practices: https://docs.celeryq.dev/en/stable/userguide/tasks.html#best-practices

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `tests/unit/test_orchestrator.py`, `tests/unit/test_pipeline_tasks.py`
  - [ ] `uv run pytest tests/unit/test_orchestrator.py -v` → PASS
  - [ ] `uv run pytest tests/unit/test_pipeline_tasks.py -v` → PASS

  **QA Scenarios:**

  ```
  Scenario: Full pipeline happy path — content flows fetched to indexed
    Tool: Bash
    Steps:
      1. POST /api/v1/pipeline/process -d '{"content_id":"test-001"}'
      2. Poll GET /api/v1/content/test-001 every 5s for 30s
      3. Assert pipeline_status="indexed", all 4 stages in history
    Expected: Content reaches indexed with all intermediate states
    Evidence: .sisyphus/evidence/task-13-pipeline-happy-path.json

  Scenario: Pipeline failure + retry
    Tool: Bash
    Steps:
      1. POST content that triggers gatekeeper failure
      2. Assert status="failed", failed_at_stage="gatekeeper"
      3. POST /api/v1/pipeline/retry/{content_id}
      4. Assert content eventually reaches "indexed"
    Expected: Recovery via retry mechanism
    Evidence: .sisyphus/evidence/task-13-pipeline-retry.json
  ```

  **Commit**: YES
  - Message: `feat(pipeline): orchestrator state machine + Celery task dispatch`
  - Files: `src/pipeline/orchestrator.py`, `src/pipeline/tasks.py`, `src/pipeline/scheduler.py`
  - Pre-commit: `uv run pytest tests/unit/test_orchestrator.py tests/unit/test_pipeline_tasks.py -v`

- [ ] 14. Telegram Bot — aiogram + Feedback Handler

  **What to do**:
  - Create `src/bot/main.py`: aiogram bot (webhook mode, port 8081, separate Docker service)
    - Register handlers: `/start`, `/help`, `/settings`, `/status`
    - Health check at `/health` for Docker healthcheck
  - Create `src/bot/handlers/push.py`: Push notification handler:
    - `send_push(user_id, content)`: Format content into Telegram card (DESIGN.md:526-560)
    - Inline keyboard: 👍高质量 | ⏰稍后再看 | 📖已知晓 | 👎无价值 | ❓解释概念 | 💬追问
    - Rate limits: max 1 msg/sec per user, 30 msgs/sec total
  - Create `src/bot/handlers/feedback.py`: Callback query handler:
    - Routes: high_quality → mark valued; read_later → re-queue; already_known → mark known;
      low_value → mark rejected; explain_concept → placeholder; discuss → placeholder
    - Stores all feedback in `content_feedback` table
  - Create `src/bot/handlers/commands.py`: /start, /help, /settings, /status
  - TDD: Test message formatting, callback routing, rate limiting

  **Must NOT do**:
  - Do NOT implement knowledge graph updates on feedback (Phase 2-3)
  - Do NOT implement "explain concept" QA flow (Phase 4, Task 52)
  - Do NOT use polling mode — webhook only
  - Do NOT run bot inside FastAPI — separate Docker service

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Telegram bot with webhooks, inline keyboards, feedback routing
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T13, T15)
  - **Parallel Group**: Wave 0.3
  - **Blocks**: Tasks 16, 23, 57
  - **Blocked By**: Tasks 1, 3, 6

  **References**:

  **Pattern References**:
  - `DESIGN.md:524-596` — Telegram push card format (3 card types)
  - `DESIGN.md:812-860` — Feedback types and skill system
  - `src/schemas/feedback.py` (T3) — FeedbackSchema, FeedbackType enum
  - `docker-compose.yml` (T1) — Bot service definition (port 8081)

  **External References**:
  - aiogram docs: https://docs.aiogram.dev/en/latest/ — Webhook, InlineKeyboardMarkup, CallbackQuery

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `tests/unit/test_bot_handlers.py`, `tests/unit/test_bot_feedback.py`
  - [ ] `uv run pytest tests/unit/test_bot_handlers.py -v` → PASS
  - [ ] `uv run pytest tests/unit/test_bot_feedback.py -v` → PASS

  **QA Scenarios:**

  ```
  Scenario: Bot responds to /start command
    Tool: Bash (curl webhook simulator)
    Steps:
      1. POST http://localhost:8081/webhook with /start message payload
      2. Assert 200 response
      3. Check logs for "Processed /start for user 123"
    Expected: Bot sends welcome message
    Evidence: .sisyphus/evidence/task-14-bot-start.txt

  Scenario: Feedback callback records to DB
    Tool: Bash
    Steps:
      1. Simulate callback_query data="feedback:high_quality:content-001"
      2. SELECT feedback_type FROM content_feedback WHERE content_id='content-001'
      3. Assert feedback_type='high_quality', timestamp recent
    Expected: Feedback recorded correctly
    Evidence: .sisyphus/evidence/task-14-feedback-callback.json
  ```

  **Commit**: YES
  - Message: `feat(bot): Telegram bot with aiogram + webhook + feedback handler`
  - Files: `src/bot/main.py`, `src/bot/handlers/`
  - Pre-commit: `uv run pytest tests/unit/test_bot_handlers.py tests/unit/test_bot_feedback.py -v`

- [ ] 15. Celery Beat Scheduling + Source Management API

  **What to do**:
  - Create `src/api/v1/sources.py`: Source CRUD endpoints:
    - POST/GET/PUT/DELETE for content sources (RSS URL, arXiv query)
    - Each source: `type`, `config` (JSON), `enabled`, `fetch_interval_minutes`
  - Enhance `src/pipeline/scheduler.py` (from T13):
    - Celery Beat reads active sources from DB (not hardcoded)
    - Per-source intervals (default 30min), stagger with random jitter 0-5min
  - Create `src/api/v1/pipeline.py`: Pipeline control endpoints:
    - POST process, GET status, POST retry/{content_id}
  - TDD: Test source CRUD, scheduler, pipeline control

  **Must NOT do**:
  - Do NOT implement time-window scheduling (Phase 1, Task 24)
  - Do NOT add Meilisearch indexing triggers
  - Do NOT implement push notification scheduling

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Standard CRUD + Celery Beat config
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T13, T14)
  - **Parallel Group**: Wave 0.3
  - **Blocks**: Tasks 17, 24
  - **Blocked By**: Tasks 1, 6, 12

  **References**:
  - `src/api/v1/` (T12) — API route pattern
  - `src/models/source.py` (T2) — Source model
  - Celery Beat: https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `tests/unit/test_source_api.py`, `tests/unit/test_scheduler.py`
  - [ ] `uv run pytest tests/unit/test_source_api.py -v` → PASS

  **QA Scenarios:**

  ```
  Scenario: Source CRUD lifecycle
    Tool: Bash
    Steps:
      1. POST /api/v1/sources with RSS source → 201
      2. GET /api/v1/sources → list contains new source
      3. PUT /api/v1/sources/{id} enabled=false → 200
      4. DELETE /api/v1/sources/{id} → 204
    Expected: Full CRUD works
    Evidence: .sisyphus/evidence/task-15-source-crud.json

  Scenario: Pipeline status endpoint
    Tool: Bash
    Steps:
      1. GET /api/v1/pipeline/status
      2. Assert queued/processing/completed/failed counts
    Expected: Accurate state distribution
    Evidence: .sisyphus/evidence/task-15-pipeline-status.json
  ```

  **Commit**: YES
  - Message: `feat(api): source management + pipeline control + Celery Beat`
  - Files: `src/api/v1/sources.py`, `src/api/v1/pipeline.py`, `src/pipeline/scheduler.py`
  - Pre-commit: `uv run pytest tests/unit/test_source_api.py tests/unit/test_scheduler.py -v`

- [ ] 16. Telegram Push Service — Content Delivery

  **What to do**:
  - Create `src/services/push.py`: `PushService`:
    - `get_next_push_batch(user_id, limit=5)`: content status=indexed, not pushed, ORDER BY quality_score DESC
    - `format_push_card(content)`: Jinja2 template `prompts/push_card.j2`
    - `deliver_push(user_id, content_list)`: Send via bot, record timestamps
    - Rate limiting: 1 msg/sec per user
  - Create `prompts/push_card.j2`: Card template (DESIGN.md:526-560)
    - Dynamic sections by content type (deep_knowledge/time_sensitive/thought_provoking)
  - Add `task_push_batch(user_id)` to pipeline tasks, wire into Celery Beat
  - TDD: Test card formatting per type, batch selection

  **Must NOT do**:
  - Do NOT implement P_score ranking (Phase 1, Task 20)
  - Do NOT implement time-window scheduling (Phase 1, Task 24)
  - Do NOT implement ε-greedy exploration (Phase 4, Task 51)
  - Simple quality_score DESC only

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Template + query + delivery — straightforward
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T17)
  - **Parallel Group**: Wave 0.4
  - **Blocks**: Tasks 20, 23, 24
  - **Blocked By**: Tasks 12, 14, 15

  **References**:
  - `DESIGN.md:524-596` — Card format templates
  - `src/bot/handlers/push.py` (T14) — send_push interface
  - `prompts/` (T5) — Jinja2 conventions

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `tests/unit/test_push_service.py`
  - [ ] `uv run pytest tests/unit/test_push_service.py -v` → PASS

  **QA Scenarios:**

  ```
  Scenario: Push delivers content batch
    Tool: Bash
    Steps:
      1. POST /api/v1/push/trigger user_id=test-user, limit=3
      2. Check bot logs for 3 sends
      3. SELECT COUNT(*) FROM push_history WHERE user_id='test-user' → 3
    Expected: 3 items pushed and recorded
    Evidence: .sisyphus/evidence/task-16-push-delivery.json

  Scenario: Card format matches design
    Tool: Bash
    Steps:
      1. GET /api/v1/push/preview?content_id=test-001
      2. Assert title, summary, push_reason, reading_advice present
      3. Assert 6 inline keyboard buttons
    Expected: Card matches DESIGN.md:526-560
    Evidence: .sisyphus/evidence/task-16-card-format.txt
  ```

  **Commit**: YES
  - Message: `feat(push): Telegram push service + card templates + batch delivery`
  - Files: `src/services/push.py`, `prompts/push_card.j2`
  - Pre-commit: `uv run pytest tests/unit/test_push_service.py -v`

- [ ] 17. Phase 0 Integration Tests + E2E Smoke Test

  **What to do**:
  - Create `tests/integration/test_phase0_e2e.py`: End-to-end pipeline test:
    - Start from adding RSS source, trigger fetch, verify content flows through all 4 pipeline stages
    - Verify content appears in DB with status=indexed, quality score assigned
    - Verify Telegram push can be triggered for indexed content
  - Create `tests/integration/test_pipeline_integration.py`:
    - Test gatekeeper → understanding → scoring chain with real DB (test DB)
    - Test failure recovery: inject failure at each stage, verify retry works
    - Test concurrent processing: multiple content items in pipeline simultaneously
  - Create `tests/integration/test_bot_integration.py`:
    - Test bot webhook receives and processes feedback
    - Test feedback updates content_feedback table
  - Docker Compose smoke test script `scripts/smoke_test.sh`:
    - `docker compose up -d`, wait for health, curl /health, fetch RSS, check pipeline, cleanup
  - TDD: Integration tests require test DB + Redis (docker compose test profile)

  **Must NOT do**:
  - Do NOT test Meilisearch (not in Phase 0)
  - Do NOT test Neo4j (not in Phase 0)
  - Do NOT test Next.js frontend (not in Phase 0)
  - Do NOT mock services — integration tests use real services with test DB

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: E2E tests require careful orchestration of multiple services
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T18)
  - **Parallel Group**: Wave 0.4
  - **Blocks**: Tasks 19-26 (Phase 1)
  - **Blocked By**: Tasks 13, 14, 15, 16

  **References**:
  - All Phase 0 services (T1-T16)
  - `docker-compose.yml` (T1) — Service orchestration

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `tests/integration/test_phase0_e2e.py`
  - [ ] `uv run pytest tests/integration/ -v` → ALL PASS

  **QA Scenarios:**

  ```
  Scenario: Full Phase 0 smoke test
    Tool: Bash
    Steps:
      1. docker compose up -d && sleep 20
      2. curl -sf http://localhost:8000/health → {"status":"ok"}
      3. POST /api/v1/sources with HN RSS feed
      4. POST /api/v1/connectors/rss/fetch → items fetched
      5. Wait 60s, GET /api/v1/content?status=indexed → at least 1 item
      6. docker compose down
    Expected: Complete pipeline from fetch to indexed
    Evidence: .sisyphus/evidence/task-17-smoke-test.txt

  Scenario: Pipeline handles concurrent content
    Tool: Bash
    Steps:
      1. Fetch 10 RSS items simultaneously
      2. Wait 120s for pipeline processing
      3. Assert all 10 items have pipeline_status in (indexed, failed)
      4. Assert no items stuck in intermediate state
    Expected: All items processed without deadlock
    Evidence: .sisyphus/evidence/task-17-concurrent.json
  ```

  **Commit**: YES
  - Message: `test(e2e): Phase 0 integration tests + smoke test script`
  - Files: `tests/integration/`, `scripts/smoke_test.sh`
  - Pre-commit: `uv run pytest tests/ -v`

- [ ] 18. Update DESIGN.md — Fix 9 Identified Inconsistencies

  **What to do**:
  Fix these 9 inconsistencies identified during planning:
  1. **Gatekeeper model**: Change Qwen-7B references to Qwen-1.5B/3B (user has RTX 4060 Laptop)
  2. **AI provider**: Update Claude/OpenAI references to DeepSeek API as primary
  3. **Spaced repetition**: Upgrade Ebbinghaus references to FSRS algorithm
  4. **Graph clustering**: Add Leiden community detection via NetworkX+leidenalg (NOT Neo4j GDS)
  5. **Telegram framework**: Specify aiogram (Python, async) instead of generic reference
  6. **MVP connectors**: Clarify Phase 0 = RSS/Atom + arXiv only
  7. **Local model size**: Clarify 1.5B/3B not 7B for gatekeeper (VRAM/thermal constraints)
  8. **Task queue**: Confirm Celery (Python) not BullMQ, no chains
  9. **Neo4j GDS licensing**: Add note about Enterprise-only algorithms, use Python-side NetworkX
  - Each fix: find the specific DESIGN.md section, update with correct information
  - Preserve document structure and Chinese language

  **Must NOT do**:
  - Do NOT restructure the entire document
  - Do NOT change the phase structure
  - Do NOT add new sections — only correct existing content
  - Do NOT translate to English

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Search-and-replace fixes in a single markdown file
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T17)
  - **Parallel Group**: Wave 0.4
  - **Blocks**: None (informational)
  - **Blocked By**: None (can start anytime)

  **References**:
  - `DESIGN.md` — Full document, all 9 inconsistency locations
  - `.sisyphus/drafts/alice-ai-secretary.md:79-88` — List of 9 issues

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: All 9 inconsistencies fixed
    Tool: Bash (grep)
    Steps:
      1. grep -i 'qwen-7b\|qwen 7b' DESIGN.md → 0 matches
      2. grep -i 'claude\|openai' DESIGN.md → 0 matches (except historical references)
      3. grep -i 'ebbinghaus' DESIGN.md → replaced with FSRS or both mentioned
      4. grep -i 'bullmq' DESIGN.md → 0 matches
      5. grep 'GDS' DESIGN.md → notes about Python-side alternative
    Expected: All 9 corrections verified via text search
    Evidence: .sisyphus/evidence/task-18-design-fixes.txt
  ```

  **Commit**: YES
  - Message: `docs: update DESIGN.md - fix 9 inconsistencies from planning review`
  - Files: `DESIGN.md`
  - Pre-commit: none

---

### Phase 1 — Intelligence Layer

- [ ] 19. 7-Dimension Quality Scoring Formula

  **What to do**:
  - Replace simple LLM score (T11) with multi-dimension weighted scoring:
    - `Q_total = Σ(w_i · q_i)` with 7 dimensions (DESIGN.md:254-270):
      - Substance (w=0.25), Density (w=0.15), Credibility (w=0.15), Novelty (w=0.20), Actionability (w=0.10), Social Signal (w=0.10), Timeliness (w=0.05)
    - Each dimension scored 0-1 by DeepSeek via structured output
    - Prompt template `prompts/quality_score_7d.j2` with dimension-specific rubrics
    - Store per-dimension scores in new `content_quality_dimensions` table
    - Novelty dimension: compare against user's known concepts (placeholder — full in Phase 2)
    - Social Signal: parse source metadata (stars, upvotes, citations) where available
  - Configurable weights via `src/config/scoring.py` (env overrides)
  - Backward-compatible: old single score = Q_total (migration)
  - TDD: Test each dimension scorer individually, test weighted aggregation

  **Must NOT do**:
  - Do NOT implement real novelty comparison against user KG (Phase 2, Task 32)
  - Do NOT scrape external platforms for social signals — use source metadata only

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Multi-dimension scoring with formula implementation requires precision
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T20, T21, T22)
  - **Parallel Group**: Wave 1.1
  - **Blocks**: Tasks 20, 32
  - **Blocked By**: Tasks 11, 17

  **References**:
  - `DESIGN.md:254-270` — Quality scoring dimensions table with weights
  - `src/services/scoring.py` (T11) — Simple scorer to extend
  - `src/llm/deepseek.py` (T4) — Structured output for dimension extraction

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `tests/unit/test_quality_scoring_7d.py`
  - [ ] `uv run pytest tests/unit/test_quality_scoring_7d.py -v` → PASS

  **QA Scenarios:**

  ```
  Scenario: 7-dimension score computed correctly
    Tool: Bash
    Steps:
      1. POST /api/v1/scoring/analyze with test article text
      2. Assert response has 7 dimension scores (each 0-1)
      3. Assert Q_total = weighted sum matches manual calculation
      4. Assert dimensions stored in content_quality_dimensions table
    Expected: All 7 dimensions scored, total matches formula
    Evidence: .sisyphus/evidence/task-19-7d-scoring.json

  Scenario: Configurable weights change total score
    Tool: Bash
    Steps:
      1. Set SCORING_WEIGHT_SUBSTANCE=0.5 env var
      2. Re-score same content
      3. Assert Q_total differs from default weights
    Expected: Custom weights properly applied
    Evidence: .sisyphus/evidence/task-19-custom-weights.json
  ```

  **Commit**: YES
  - Message: `feat(scoring): 7-dimension quality scoring formula`
  - Files: `src/services/scoring.py`, `src/config/scoring.py`, `prompts/quality_score_7d.j2`
  - Pre-commit: `uv run pytest tests/unit/test_quality_scoring_7d.py -v`

- [ ] 20. Push Priority Ranking Engine — P_score Formula

  **What to do**:
  - Create `src/services/ranking.py`: `RankingService`:
    - Implements `P_score = Q_content · R_relevance · T_timing · D_decay · U_urgency + ε_explore`
    - `Q_content`: from 7-dimension scorer (T19)
    - `R_relevance`: placeholder = 1.0 (full implementation in Phase 2 with KG, Task 32)
    - `T_timing`: time-window match (T24 implements scheduling, this computes the factor)
    - `D_decay`: exponential decay for time-sensitive content, slow decay for knowledge
    - `U_urgency`: boost for DDL-proximate or breaking-news content
    - `ε_explore`: placeholder = 0 (Phase 4, Task 51 implements ε-greedy)
  - Replace simple quality_score ordering in PushService (T16) with P_score ranking
  - Store P_score in content table, recompute on schedule (Celery task)
  - TDD: Test each factor independently, test combined ranking order

  **Must NOT do**:
  - Do NOT implement R_relevance KG matching (Phase 2)
  - Do NOT implement ε-greedy exploration (Phase 4)
  - Do NOT implement user state-based T_timing (Phase 3)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Multi-factor ranking formula with mathematical precision
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T19, T21, T22)
  - **Parallel Group**: Wave 1.1
  - **Blocks**: Tasks 24, 32, 51
  - **Blocked By**: Tasks 11, 16, 17

  **References**:
  - `DESIGN.md:400-414` — P_score formula and factor definitions
  - `DESIGN.md:416-442` — R_relevance and KG_match formulas
  - `src/services/push.py` (T16) — PushService to integrate with

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `tests/unit/test_ranking.py`
  - [ ] `uv run pytest tests/unit/test_ranking.py -v` → PASS

  **QA Scenarios:**

  ```
  Scenario: Ranking orders content by P_score
    Tool: Bash
    Steps:
      1. Insert 5 test content items with different quality scores and timestamps
      2. POST /api/v1/ranking/compute
      3. GET /api/v1/content?order_by=p_score&limit=5
      4. Assert order: high-quality recent > high-quality old > medium > low
    Expected: P_score ordering reflects formula correctly
    Evidence: .sisyphus/evidence/task-20-ranking-order.json

  Scenario: Time decay affects ranking
    Tool: Bash
    Steps:
      1. Insert time-sensitive content from 1 hour ago and 7 days ago
      2. Both have same quality score
      3. Assert 1-hour-ago item has higher P_score
    Expected: Decay factor differentiates stale from fresh content
    Evidence: .sisyphus/evidence/task-20-time-decay.json
  ```

  **Commit**: YES
  - Message: `feat(ranking): push priority ranking engine with P_score formula`
  - Files: `src/services/ranking.py`, `src/services/push.py`
  - Pre-commit: `uv run pytest tests/unit/test_ranking.py -v`

- [ ] 21. Meilisearch Integration + Full-Text Indexing

  **What to do**:
  - Add Meilisearch service to `docker-compose.yml` (port 7700)
  - Create `src/services/search.py`: `SearchService`:
    - `index_content(content)`: Push content to Meilisearch index on pipeline completion
    - `search(query, filters, limit)`: Full-text search with highlighting
    - Index fields: title, summary, key_points, source_url, content_type, quality_score
    - Filterable attributes: content_type, quality_score range, source_type, pipeline_status
    - Sortable: quality_score, created_at, p_score
  - Hook into pipeline: after `indexed` state, also push to Meilisearch
  - Create `src/api/v1/search.py`: Search endpoint (Task 25 expands this)
  - TDD: Test indexing, search queries, filters, highlighting

  **Must NOT do**:
  - Do NOT use Elasticsearch — Meilisearch only (lightweight, simpler)
  - Do NOT implement semantic search (no vector DB constraint)
  - Do NOT index knowledge graph data (Phase 2)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: New service integration with Docker + Python client
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T19, T20, T22)
  - **Parallel Group**: Wave 1.1
  - **Blocks**: Tasks 25, 33
  - **Blocked By**: Tasks 12, 17

  **References**:
  - `DESIGN.md:273-281` — Indexing strategy (full-text search requirement)
  - `docker-compose.yml` (T1) — Add Meilisearch service
  - Meilisearch Python: https://github.com/meilisearch/meilisearch-python

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `tests/unit/test_search_service.py`
  - [ ] `uv run pytest tests/unit/test_search_service.py -v` → PASS

  **QA Scenarios:**

  ```
  Scenario: Content searchable after indexing
    Tool: Bash
    Steps:
      1. Index 10 test articles via pipeline
      2. GET /api/v1/search?q=transformer → assert matches returned
      3. Assert results have highlighted snippets
      4. curl http://localhost:7700/indexes → content index exists
    Expected: Full-text search returns relevant results
    Evidence: .sisyphus/evidence/task-21-search.json

  Scenario: Filtered search by content type
    Tool: Bash
    Steps:
      1. GET /api/v1/search?q=AI&content_type=deep_knowledge
      2. Assert all results have content_type="deep_knowledge"
    Expected: Filters correctly narrow results
    Evidence: .sisyphus/evidence/task-21-filtered-search.json
  ```

  **Commit**: YES
  - Message: `feat(search): Meilisearch integration + full-text indexing`
  - Files: `src/services/search.py`, `docker-compose.yml`
  - Pre-commit: `uv run pytest tests/unit/test_search_service.py -v`

- [ ] 22. Content Deduplication — URL Normalization + SimHash

  **What to do**:
  - Create `src/services/dedup.py`: `DeduplicationService`:
    - URL normalization: strip tracking params (utm_*), normalize scheme/trailing slash
    - Exact URL match: check against DB before processing (fast path)
    - SimHash for near-duplicate detection: compute 64-bit fingerprint of content text
    - Similarity threshold: SimHash hamming distance ≤ 3 = duplicate
    - Store fingerprints in `content.simhash` column
    - Hook into pipeline: check dedup BEFORE gatekeeper stage
  - Create `src/utils/url.py`: URL normalization utilities
  - TDD: Test URL normalization, SimHash computation, duplicate detection

  **Must NOT do**:
  - Do NOT use vector similarity (no vector DB)
  - Do NOT implement cross-language dedup
  - Do NOT block content silently — mark as duplicate with reference to original

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: SimHash algorithm + URL normalization — moderate algorithmic complexity
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T19, T20, T21)
  - **Parallel Group**: Wave 1.1
  - **Blocks**: Task 26
  - **Blocked By**: Tasks 12, 17

  **References**:
  - `src/services/storage.py` (T12) — Content storage for fingerprint column
  - SimHash algorithm: https://en.wikipedia.org/wiki/SimHash

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `tests/unit/test_dedup.py`
  - [ ] `uv run pytest tests/unit/test_dedup.py -v` → PASS

  **QA Scenarios:**

  ```
  Scenario: Exact URL duplicate detected
    Tool: Bash
    Steps:
      1. Store content with URL https://example.com/article?utm_source=twitter
      2. Attempt to store https://example.com/article
      3. Assert second attempt flagged as duplicate, references original
    Expected: URL normalization catches tracking-param variants
    Evidence: .sisyphus/evidence/task-22-url-dedup.json

  Scenario: SimHash near-duplicate detected
    Tool: Bash
    Steps:
      1. Store article A (500 words)
      2. Store article B (same content with 5% word changes)
      3. Assert B flagged as near-duplicate of A
    Expected: SimHash detects paraphrased content
    Evidence: .sisyphus/evidence/task-22-simhash-dedup.json
  ```

  **Commit**: YES
  - Message: `feat(dedup): URL normalization + SimHash near-duplicate detection`
  - Files: `src/services/dedup.py`, `src/utils/url.py`
  - Pre-commit: `uv run pytest tests/unit/test_dedup.py -v`

- [ ] 23. Enhanced Telegram Card Formatting

  **What to do**:
  - Enhance `src/bot/handlers/push.py` and `prompts/push_card.j2`:
    - Implement all 3 card types from DESIGN.md:524-596:
      - Deep Knowledge: title + AI summary + core insights + prerequisites + reading advice + 6 buttons
      - Time-Sensitive: one-line summary + What + Impact + link + 2 buttons (✅已了解 | 📌需要跟进)
      - Thought-Provoking: title + thought summary + push reason + 4 buttons
    - Auto-select card type based on content_type classification
    - Generate push_reason via DeepSeek: why this content matters for THIS user right now
    - Generate reading_advice: which sections to read, estimated time
    - Format with Telegram MarkdownV2 (escape special chars)
  - TDD: Test each card type rendering, special char escaping

  **Must NOT do**:
  - Do NOT implement "explain concept" flow (Phase 4)
  - Do NOT implement personalized push_reason using KG (Phase 2) — use generic reasons

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Template enhancement — mostly Jinja2 + formatting
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T24)
  - **Parallel Group**: Wave 1.2
  - **Blocks**: Task 26
  - **Blocked By**: Tasks 14, 16, 19

  **References**:
  - `DESIGN.md:524-596` — All 3 card templates with examples
  - `src/bot/handlers/push.py` (T14) — Existing push handler
  - `prompts/push_card.j2` (T16) — Base template to extend

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `tests/unit/test_card_formatting.py`
  - [ ] `uv run pytest tests/unit/test_card_formatting.py -v` → PASS

  **QA Scenarios:**

  ```
  Scenario: Deep knowledge card rendered correctly
    Tool: Bash
    Steps:
      1. GET /api/v1/push/preview?content_id=deep-001&type=deep_knowledge
      2. Assert response contains: AI summary, core insights, reading advice
      3. Assert 6 inline keyboard buttons present
      4. Assert MarkdownV2 valid (no unescaped special chars)
    Expected: Complete deep knowledge card matching DESIGN.md:528-560
    Evidence: .sisyphus/evidence/task-23-deep-card.txt

  Scenario: Time-sensitive card is minimal
    Tool: Bash
    Steps:
      1. GET /api/v1/push/preview?content_id=news-001&type=time_sensitive
      2. Assert compact format: What + Impact + link only
      3. Assert only 2 buttons
    Expected: Minimal card for time-sensitive content
    Evidence: .sisyphus/evidence/task-23-time-card.txt
  ```

  **Commit**: YES
  - Message: `feat(bot): enhanced Telegram card formatting for 3 content types`
  - Files: `src/bot/handlers/push.py`, `prompts/push_card.j2`
  - Pre-commit: `uv run pytest tests/unit/test_card_formatting.py -v`

- [ ] 24. Time-Window Push Scheduling

  **What to do**:
  - Create `src/services/scheduler.py`: `PushScheduler`:
    - Time-window rules (DESIGN.md:555-590 + README concepts):
      - Weekday morning (8-10am): high-priority deep knowledge
      - Weekday afternoon (2-4pm): practical guidance, tools
      - Evening (8-11pm): thought-provoking, light reading
      - Weekend: exploration content, weekly summaries
    - User-configurable quiet hours (default 11pm-7am)
    - User-configurable push frequency (default 3x/day)
    - T_timing factor for ranking (integrates with T20 P_score)
  - Enhance Celery Beat: schedule push batches at configured time windows
  - Create `src/api/v1/settings.py`: User push settings endpoints:
    - GET/PUT push preferences (frequency, quiet hours, time windows)
  - TDD: Test time-window matching, quiet hours, schedule generation

  **Must NOT do**:
  - Do NOT implement user state-based scheduling (Phase 3, Task 42)
  - Do NOT implement energy/mood detection

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Scheduling logic with timezone handling + user preferences
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T23)
  - **Parallel Group**: Wave 1.2
  - **Blocks**: Task 26, 42
  - **Blocked By**: Tasks 15, 16, 20

  **References**:
  - `DESIGN.md:443-470` — Push throttling and time-window logic
  - `src/services/ranking.py` (T20) — T_timing factor integration
  - `src/pipeline/scheduler.py` (T15) — Celery Beat base

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `tests/unit/test_push_scheduler.py`
  - [ ] `uv run pytest tests/unit/test_push_scheduler.py -v` → PASS

  **QA Scenarios:**

  ```
  Scenario: Morning push delivers deep knowledge only
    Tool: Bash
    Steps:
      1. Set test time to weekday 9am
      2. Trigger push batch
      3. Assert all pushed content is type=deep_knowledge or high P_score
    Expected: Time window filters content type appropriately
    Evidence: .sisyphus/evidence/task-24-morning-push.json

  Scenario: Quiet hours block all pushes
    Tool: Bash
    Steps:
      1. Set test time to 1am
      2. Trigger push batch
      3. Assert 0 pushes sent, response indicates quiet hours
    Expected: No pushes during quiet hours
    Evidence: .sisyphus/evidence/task-24-quiet-hours.json
  ```

  **Commit**: YES
  - Message: `feat(push): time-window scheduling + user push preferences`
  - Files: `src/services/scheduler.py`, `src/api/v1/settings.py`
  - Pre-commit: `uv run pytest tests/unit/test_push_scheduler.py -v`

- [ ] 25. Search API Endpoints

  **What to do**:
  - Enhance `src/api/v1/search.py` (from T21):
    - `GET /api/v1/search?q=...&type=...&min_score=...&limit=...&offset=...`
    - Pagination with cursor-based or offset-based pagination
    - Faceted search: count by content_type, source_type
    - Auto-suggest / autocomplete from Meilisearch
    - Search history: store recent queries per user
  - TDD: Test search endpoint, pagination, facets, autocomplete

  **Must NOT do**:
  - Do NOT implement GraphRAG query (Phase 2, Task 33)
  - Do NOT implement semantic search

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Standard API endpoint wrapping Meilisearch client
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T26)
  - **Parallel Group**: Wave 1.2 (late)
  - **Blocks**: Task 26
  - **Blocked By**: Tasks 21, 22

  **References**:
  - `src/services/search.py` (T21) — SearchService interface
  - Meilisearch search params: https://www.meilisearch.com/docs/reference/api/search

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `tests/unit/test_search_api.py`
  - [ ] `uv run pytest tests/unit/test_search_api.py -v` → PASS

  **QA Scenarios:**

  ```
  Scenario: Search with pagination
    Tool: Bash
    Steps:
      1. Index 20 articles
      2. GET /api/v1/search?q=AI&limit=5&offset=0 → 5 results + total count
      3. GET /api/v1/search?q=AI&limit=5&offset=5 → next 5 results
    Expected: Paginated results with correct total
    Evidence: .sisyphus/evidence/task-25-search-pagination.json
  ```

  **Commit**: YES (groups with T21)
  - Message: `feat(api): search endpoints with pagination + facets`
  - Files: `src/api/v1/search.py`
  - Pre-commit: `uv run pytest tests/unit/test_search_api.py -v`

- [ ] 26. Phase 1 Integration Tests

  **What to do**:
  - Create `tests/integration/test_phase1_e2e.py`:
    - Test: content flows through pipeline with 7-dimension scoring
    - Test: P_score ranking orders push queue correctly
    - Test: Meilisearch indexes and returns searchable content
    - Test: Dedup catches URL variants and SimHash near-duplicates
    - Test: Time-window scheduling delivers right content at right time
    - Test: Enhanced Telegram cards render all 3 types
  - Verify all Phase 0+1 services work together
  - Performance baseline: measure pipeline throughput (items/minute)

  **Must NOT do**:
  - Do NOT test Neo4j (Phase 2)
  - Do NOT test frontend (Phase 2)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Cross-service integration testing requires orchestration
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (after Wave 1.2)
  - **Blocks**: Phase 2 tasks (T27+)
  - **Blocked By**: Tasks 19-25

  **References**:
  - All Phase 1 tasks (T19-T25)
  - `tests/integration/test_phase0_e2e.py` (T17) — Integration test patterns

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `tests/integration/test_phase1_e2e.py`
  - [ ] `uv run pytest tests/integration/test_phase1_e2e.py -v` → ALL PASS

  **QA Scenarios:**

  ```
  Scenario: Full Phase 1 pipeline
    Tool: Bash
    Steps:
      1. docker compose up -d (all services including Meilisearch)
      2. Add RSS source, fetch 5 items
      3. Wait for pipeline: all items reach indexed with 7D scores
      4. Search via Meilisearch → results found
      5. Trigger ranked push → items delivered in P_score order
    Expected: Complete Phase 1 pipeline works end-to-end
    Evidence: .sisyphus/evidence/task-26-phase1-e2e.json
  ```

  **Commit**: YES
  - Message: `test(e2e): Phase 1 integration tests`
  - Files: `tests/integration/test_phase1_e2e.py`
  - Pre-commit: `uv run pytest tests/ -v`

---

### Phase 2 — Knowledge Engine

- [ ] 27. Neo4j Setup + Schema + Python Driver

  **What to do**:
  - Add Neo4j service to `docker-compose.yml` (ports 7474 browser, 7687 bolt)
  - Create `src/graph/client.py`: Neo4j driver wrapper:
    - Connection pool management, health check
    - `execute_query(cypher, params)`: Run Cypher queries
    - `ensure_schema()`: Create indexes and constraints on startup
  - Create `src/graph/schema.py`: Graph schema definitions:
    - Node labels: `Concept`, `Method`, `Tool`, `Theory`, `User`, `Content`
    - Relationship types: `KNOWS`, `PREREQUISITE_OF`, `EXTENDS`, `APPLIES_TO`, `DISCUSSES`, `CONTRASTS`
    - Constraints: unique concept names (English canonical), unique content IDs
    - Indexes: concept name, content ID, user ID
  - Create `src/graph/repository.py`: Graph CRUD operations:
    - `upsert_concept(name, type, aliases)`, `create_relationship(from, to, type)`
    - `get_user_knowledge(user_id)`, `get_content_subgraph(content_id)`
  - Language normalization: concept nodes use English canonical names, Chinese aliases stored as properties
  - TDD: Test schema creation, CRUD ops, constraint enforcement

  **Must NOT do**:
  - Do NOT use Neo4j GDS (Enterprise only) — Metis guardrail
  - Do NOT implement graph algorithms here (T45 uses Python-side NetworkX)
  - Do NOT implement content-to-graph extraction (T28)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: New database integration with schema design
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T29, T30)
  - **Parallel Group**: Wave 2.1
  - **Blocks**: Tasks 28, 31, 32, 33, 37, 45
  - **Blocked By**: Tasks 17, 26 (Phase 1 complete)

  **References**:
  - `DESIGN.md:234-241` — ContentSubgraph interface
  - `DESIGN.md:277-280` — Knowledge graph storage requirements
  - `DESIGN.md:284-340` — User modeling three-layer architecture
  - Neo4j Python driver: https://neo4j.com/docs/python-manual/current/

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `tests/unit/test_graph_client.py`, `tests/integration/test_neo4j.py`
  - [ ] `uv run pytest tests/unit/test_graph_client.py -v` → PASS
  - [ ] `uv run pytest tests/integration/test_neo4j.py -v` → PASS (requires Neo4j)

  **QA Scenarios:**

  ```
  Scenario: Neo4j schema created on startup
    Tool: Bash
    Steps:
      1. docker compose up neo4j -d && sleep 10
      2. Run schema migration
      3. curl http://localhost:7474 → browser accessible
      4. Cypher: SHOW CONSTRAINTS → concept uniqueness exists
    Expected: Schema with indexes and constraints
    Evidence: .sisyphus/evidence/task-27-neo4j-schema.json

  Scenario: Concept CRUD with language normalization
    Tool: Bash
    Steps:
      1. Create concept name="transformer", aliases=["变换器", "Transformer"]
      2. Query by alias "变换器" → returns same node
      3. Assert canonical name is English
    Expected: Bilingual concept resolution works
    Evidence: .sisyphus/evidence/task-27-concept-crud.json
  ```

  **Commit**: YES
  - Message: `feat(graph): Neo4j setup + schema + Python driver`
  - Files: `src/graph/`, `docker-compose.yml`
  - Pre-commit: `uv run pytest tests/unit/test_graph_client.py -v`

- [ ] 28. Content Subgraph Generation via LLM

  **What to do**:
  - Create `src/graph/extractor.py`: `SubgraphExtractor`:
    - Takes content (title + summary + key_points from understanding stage)
    - Sends to DeepSeek with `prompts/extract_subgraph.j2`
    - Returns `ContentSubgraph` (DESIGN.md:234-241):
      - nodes: [{name, type: concept|method|tool|theory}]
      - edges: [{from, to, relation: prerequisite|extends|applies_to|contrasts}]
      - difficulty: 0-1
      - entryConcepts: key prerequisite concepts
    - Normalizes concept names to English canonical (Chinese → English mapping)
    - Stores subgraph in Neo4j via graph repository (T27)
  - Hook into pipeline: after `scored` stage, extract subgraph
  - Create `prompts/extract_subgraph.j2`: LLM prompt for structured graph extraction
  - TDD: Test extraction with mock LLM responses, test normalization, test graph storage

  **Must NOT do**:
  - Do NOT extract from full-text (use summary + key_points only for cost efficiency)
  - Do NOT implement user KG matching here (T32)
  - Do NOT over-extract: max 10 concepts per content item

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: LLM-based structured extraction requires careful prompt engineering
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T31)
  - **Parallel Group**: Wave 2.2
  - **Blocks**: Tasks 32, 33, 37
  - **Blocked By**: Tasks 27, 4 (LLM client), 10 (understanding output)

  **References**:
  - `DESIGN.md:234-241` — ContentSubgraph interface definition
  - `src/llm/deepseek.py` (T4) — Structured output for graph extraction
  - `src/graph/repository.py` (T27) — Graph CRUD

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `tests/unit/test_subgraph_extractor.py`
  - [ ] `uv run pytest tests/unit/test_subgraph_extractor.py -v` → PASS

  **QA Scenarios:**

  ```
  Scenario: Subgraph extracted from technical article
    Tool: Bash
    Steps:
      1. Process article about "Attention is All You Need"
      2. GET /api/v1/content/{id}/subgraph
      3. Assert nodes include: transformer, attention, self-attention
      4. Assert edges include prerequisite relationships
      5. Assert difficulty ∈ [0, 1]
    Expected: Meaningful concept graph extracted
    Evidence: .sisyphus/evidence/task-28-subgraph-extraction.json

  Scenario: Concept names normalized to English
    Tool: Bash
    Steps:
      1. Process Chinese article about "注意力机制"
      2. Assert concept node name is "attention_mechanism" not "注意力机制"
      3. Assert Chinese alias stored as property
    Expected: English canonical names with Chinese aliases
    Evidence: .sisyphus/evidence/task-28-normalization.json
  ```

  **Commit**: YES
  - Message: `feat(graph): content subgraph generation via LLM`
  - Files: `src/graph/extractor.py`, `prompts/extract_subgraph.j2`
  - Pre-commit: `uv run pytest tests/unit/test_subgraph_extractor.py -v`

- [ ] 29. Next.js Project Scaffolding + API Client

  **What to do**:
  - Create `frontend/` directory with Next.js 14 App Router:
    - `npx create-next-app@latest frontend --typescript --tailwind --app --src-dir`
    - Add shadcn/ui: `npx shadcn-ui@latest init`
    - Add TanStack Query for data fetching
    - Add Zustand for client state management
  - Create `frontend/src/lib/api.ts`: API client:
    - Base URL configurable (localhost:8000 dev, proxy in prod)
    - Typed request/response using shared types
    - Error handling with typed error responses
    - Auth token management (simple API key for now)
  - Create `frontend/src/lib/types.ts`: Frontend type definitions matching backend schemas
  - Add `frontend` service to docker-compose.yml (port 3000)
  - Configure vitest: `frontend/vitest.config.ts`
  - TDD: Test API client, type consistency

  **Must NOT do**:
  - Do NOT use Radix UI directly — use shadcn/ui (simpler for solo dev)
  - Do NOT implement SSR for API calls — client-side fetching with TanStack Query
  - Do NOT implement auth beyond simple API key

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Frontend scaffolding with component library setup
  - **Skills**: [`frontend-ui-ux`]
    - `frontend-ui-ux`: UI/UX design patterns for component architecture

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T27, T30)
  - **Parallel Group**: Wave 2.1
  - **Blocks**: Tasks 30, 34, 35, 36
  - **Blocked By**: Tasks 26 (Phase 1 complete)

  **References**:
  - Folo UI research — Two-column layout pattern, card components
  - `src/schemas/` (T3) — Backend types to mirror
  - Next.js App Router: https://nextjs.org/docs/app

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `frontend/src/__tests__/api.test.ts`
  - [ ] `cd frontend && npx vitest run` → PASS

  **QA Scenarios:**

  ```
  Scenario: Next.js dev server starts
    Tool: Bash
    Steps:
      1. cd frontend && npm run dev &
      2. Wait 10s
      3. curl -sf http://localhost:3000 → 200 with HTML
    Expected: Next.js serves page
    Evidence: .sisyphus/evidence/task-29-nextjs-start.txt
  ```

  **Commit**: YES
  - Message: `feat(frontend): Next.js project scaffolding + API client + vitest`
  - Files: `frontend/`
  - Pre-commit: `cd frontend && npm run lint && npm run build`

- [ ] 30. Next.js Auth + Layout Shell (Folo Two-Column Pattern)

  **What to do**:
  - Create `frontend/src/app/layout.tsx`: Root layout:
    - Two-column layout inspired by Folo: sidebar (sources/nav) + main content area
    - Resizable sidebar (min 200px, max 400px)
    - Responsive: collapses to bottom nav on mobile
    - Dark/light mode toggle (Tailwind dark: classes)
  - Create `frontend/src/components/layout/sidebar.tsx`: Source sidebar:
    - List content sources with status indicators
    - Navigation: Feed, Search, Settings, Reports
    - Source filter: click source to filter feed view
  - Create `frontend/src/app/(auth)/login/page.tsx`: Simple auth:
    - API key input form (not full OAuth for MVP)
    - Store key in localStorage + TanStack Query headers
  - Create `frontend/src/components/ui/` shadcn components: Button, Card, Input, ScrollArea, etc.
  - TDD: Test layout renders, sidebar navigation, auth flow

  **Must NOT do**:
  - Do NOT implement full OAuth/session management
  - Do NOT implement the feed content yet (T34)
  - Do NOT implement settings form (T36)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Layout design + responsive UI
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T27, T29)
  - **Parallel Group**: Wave 2.1
  - **Blocks**: Tasks 34, 35, 36
  - **Blocked By**: Task 29

  **References**:
  - Folo two-column layout: `Folo/apps/desktop/layer/renderer/src/modules/entry-column/`
  - Folo card patterns: `Folo/packages/internal/components/`
  - shadcn/ui: https://ui.shadcn.com/docs

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `frontend/src/__tests__/layout.test.tsx`
  - [ ] `cd frontend && npx vitest run` → PASS

  **QA Scenarios:**

  ```
  Scenario: Two-column layout renders
    Tool: Playwright
    Steps:
      1. Navigate to http://localhost:3000
      2. Assert sidebar visible (data-testid="sidebar")
      3. Assert main content area visible
      4. Resize sidebar drag handle → sidebar width changes
    Expected: Responsive two-column layout
    Evidence: .sisyphus/evidence/task-30-layout.png

  Scenario: Dark mode toggle
    Tool: Playwright
    Steps:
      1. Click dark mode toggle button
      2. Assert document.documentElement has class "dark"
      3. Assert background color changes
    Expected: Theme switches correctly
    Evidence: .sisyphus/evidence/task-30-darkmode.png
  ```

  **Commit**: YES
  - Message: `feat(frontend): auth + two-column layout shell`
  - Files: `frontend/src/app/layout.tsx`, `frontend/src/components/layout/`
  - Pre-commit: `cd frontend && npm run lint && npm run build`

- [ ] 31. User Knowledge Graph Initial Model

  **What to do**:
  - Create `src/graph/user_kg.py`: `UserKnowledgeGraph`:
    - Initialize user node in Neo4j with profile
    - `(User)-[:KNOWS {mastery: 0-1, last_reviewed}]->(Concept)`
    - Mastery levels: 0 (unknown), 0.3 (aware), 0.6 (understands), 0.9 (mastered)
    - `add_known_concept(user_id, concept, mastery)`: Add/update knowledge edge
    - `get_knowledge_map(user_id)`: Return all known concepts with mastery levels
    - `get_knowledge_gaps(user_id, concept)`: Find missing prerequisites
  - Create `src/api/v1/knowledge.py`: User KG API:
    - GET /api/v1/user/knowledge → full knowledge map
    - POST /api/v1/user/knowledge → manually add known concept
    - GET /api/v1/user/knowledge/gaps → identified knowledge gaps
  - Seed mechanism: user provides initial areas of expertise during onboarding
  - TDD: Test knowledge CRUD, mastery updates, gap detection

  **Must NOT do**:
  - Do NOT implement automatic KG updates from feedback (T37)
  - Do NOT implement FSRS mastery decay (Phase 3, T40)
  - Do NOT implement Leiden communities (T45)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Graph data modeling + API design for knowledge representation
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T28)
  - **Parallel Group**: Wave 2.2
  - **Blocks**: Tasks 32, 37, 40, 42, 45
  - **Blocked By**: Task 27

  **References**:
  - `DESIGN.md:284-340` — User modeling three-layer architecture
  - `DESIGN.md:296-299` — Competency map layer
  - `src/graph/repository.py` (T27) — Graph CRUD base

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `tests/unit/test_user_kg.py`
  - [ ] `uv run pytest tests/unit/test_user_kg.py -v` → PASS

  **QA Scenarios:**

  ```
  Scenario: User knowledge map CRUD
    Tool: Bash
    Steps:
      1. POST /api/v1/user/knowledge -d '{"concept":"transformer","mastery":0.8}'
      2. GET /api/v1/user/knowledge → includes transformer at 0.8
      3. POST another concept "attention" at 0.6
      4. GET gaps for "multi_head_attention" → shows prerequisites
    Expected: KG tracks user knowledge with mastery levels
    Evidence: .sisyphus/evidence/task-31-user-kg.json
  ```

  **Commit**: YES
  - Message: `feat(graph): user knowledge graph model + API`
  - Files: `src/graph/user_kg.py`, `src/api/v1/knowledge.py`
  - Pre-commit: `uv run pytest tests/unit/test_user_kg.py -v`

- [ ] 32. Content-User Matching Algorithm

  **What to do**:
  - Create `src/services/matching.py`: `MatchingService`:
    - Implements `Match_score = 0.5·Prerequisite_coverage + 0.3·Concept_distance_fit + 0.2·Difficulty_fit`
    - `Prerequisite_coverage`: % of content's entry concepts user has mastery ≥ 0.3
    - `Concept_distance_fit`: graph distance from user's known concepts to content concepts
    - `Difficulty_fit`: |content.difficulty - user_average_mastery| (closer = better)
    - Recommendation threshold: Match_score ≥ θ_recommend (default 0.4), below → defer
    - Replace R_relevance placeholder in ranking (T20) with real Match_score
  - Integrate with P_score: R_relevance = Match_score
  - Full R_relevance: `R = α·KG_match + β·Working_match + γ·Preference_match + δ·Gap_fill`
    - Working_match: placeholder (Phase 3, Task 42 implements user state)
    - Preference_match: from feedback history (simple like/dislike ratio per topic)
    - Gap_fill: concepts in content that user doesn't know but has prerequisites for
  - TDD: Test each sub-score, test combined matching, test threshold deferral

  **Must NOT do**:
  - Do NOT implement Working_match fully (needs user state from Phase 3)
  - Do NOT use vector similarity — graph-based matching only

  **Recommended Agent Profile**:
  - **Category**: `ultrabrain`
    - Reason: Complex multi-factor matching algorithm with graph queries
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with T33)
  - **Parallel Group**: Wave 2.3
  - **Blocks**: Tasks 38, 42, 51
  - **Blocked By**: Tasks 27, 28, 31, 19

  **References**:
  - `DESIGN.md:416-442` — R_relevance formula, KG_match, MatchScore
  - `DESIGN.md:434-439` — Recommendation threshold logic
  - `src/services/ranking.py` (T20) — P_score R_relevance integration point
  - `src/graph/user_kg.py` (T31) — User knowledge access
  - `src/graph/extractor.py` (T28) — Content subgraph access

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `tests/unit/test_matching.py`
  - [ ] `uv run pytest tests/unit/test_matching.py -v` → PASS

  **QA Scenarios:**

  ```
  Scenario: Content matched to user knowledge
    Tool: Bash
    Steps:
      1. Seed user KG with transformer=0.8, attention=0.7
      2. Process article about "multi-head attention optimization"
      3. GET /api/v1/matching/score?content_id=X&user_id=Y
      4. Assert Match_score > 0.5 (user has prerequisites)
    Expected: High match for content user is ready for
    Evidence: .sisyphus/evidence/task-32-matching.json

  Scenario: Content deferred due to missing prerequisites
    Tool: Bash
    Steps:
      1. User KG has only basic_math=0.5
      2. Process advanced quantum computing article
      3. Assert Match_score < θ_recommend
      4. Assert content deferred, not in push queue
    Expected: Content too advanced is deferred
    Evidence: .sisyphus/evidence/task-32-deferred.json
  ```

  **Commit**: YES
  - Message: `feat(matching): content-user matching algorithm + R_relevance`
  - Files: `src/services/matching.py`
  - Pre-commit: `uv run pytest tests/unit/test_matching.py -v`

- [ ] 33. GraphRAG Hybrid Query Engine

  **What to do**:
  - Implement `src/services/graphrag_query.py` — unified query layer combining three retrieval modes:
    - **Graph traversal (50% weight)**: Query Neo4j for concept nodes within N hops of query concept, filter by mastery and relationship type. Use Cypher queries for subgraph extraction.
    - **Full-text search (30% weight)**: Query Meilisearch with rewritten query terms (LLM query rewriting via DeepSeek API). Return scored results with snippet highlights.
    - **Semantic matching (20% weight)**: Compute cosine similarity between query embedding and content embeddings stored in PostgreSQL (manual cosine on JSONB arrays). Use lightweight sentence-transformers model.
  - Implement `GraphRAGQueryEngine` class with methods:
    - `query(text: str, user_id: str, mode: QueryMode) -> list[RankedResult]`
    - `_graph_search(concepts: list[str], user_kg: UserKG) -> list[GraphHit]`
    - `_text_search(rewritten_query: str) -> list[TextHit]`
    - `_semantic_search(embedding: list[float]) -> list[SemanticHit]`
    - `_merge_and_rank(graph_hits, text_hits, semantic_hits, weights) -> list[RankedResult]`
  - Query rewriting: LLM call to expand user query into structured search terms (via `LLMClient` protocol from Task 9)
  - Implement result deduplication (same content from multiple retrieval paths)
  - Configurable weights via `src/core/config.py`: `GRAPHRAG_GRAPH_WEIGHT=0.5`, `GRAPHRAG_TEXT_WEIGHT=0.3`, `GRAPHRAG_SEMANTIC_WEIGHT=0.2`
  - TDD: Write tests first in `tests/unit/test_graphrag_query.py`:
    - Test each retrieval mode independently with mocked backends
    - Test weight-based merging produces correct rank order
    - Test deduplication removes identical content from different sources
    - Test fallback when one backend is unavailable (graceful degradation)

  **Must NOT do**:
  - Do NOT use vector database — use PostgreSQL for embeddings (per DESIGN.md constraint)
  - Do NOT use Neo4j GDS algorithms here — this is query only, not graph analytics
  - Do NOT hardcode weight values — must be configurable
  - Do NOT block on LLM query rewriting failure — fall back to raw query text

  **Recommended Agent Profile**:
  - **Category**: `ultrabrain`
    - Reason: Complex multi-source retrieval fusion with ranking algorithm requires deep algorithmic thinking
  - **Skills**: []
    - No specialized skills needed — pure Python algorithm implementation
  - **Skills Evaluated but Omitted**:
    - `playwright`: No browser interaction

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2.1 (with Tasks 34, 35, 36)
  - **Blocks**: Tasks 37, 38 (KG update needs query engine; integration tests need all components)
  - **Blocked By**: Tasks 27 (Neo4j schema), 21 (Meilisearch), 13 (content processing pipeline)

  **References**:
  **Pattern References**:
  - `src/llm/protocol.py` — LLMClient protocol for query rewriting calls (Task 4)
  - `src/pipeline/tasks.py` — How content is processed across stages and transformed for retrieval (Task 13)
  - `src/models/content.py` — Content model with embedding field (Task 3)
  - `src/graph/client.py` — Neo4j connection and Cypher execution (Task 27)
  - `src/services/search.py` — Meilisearch query API (Task 21)
  **External References**:
  - DESIGN.md:625-660 — GraphRAG query flow and storage architecture diagram
  - DESIGN.md:364-373 — Match score formula and thresholds for subgraph matching
  **WHY Each Reference Matters**:
  - LLMClient: Query rewriting uses same LLM abstraction as content processing
  - Neo4j/Meilisearch clients: Must use existing connection patterns, not create new ones
  - DESIGN.md query flow: The exact 6-step query process to implement

  **Acceptance Criteria**:
  **TDD:**
  - [ ] Test file created: `tests/unit/test_graphrag_query.py`
  - [ ] `uv run pytest tests/unit/test_graphrag_query.py -v` → PASS (8+ tests, 0 failures)
  - [ ] Tests cover: graph search, text search, semantic search, merging, deduplication, fallback

  **QA Scenarios:**
  ```
  Scenario: Happy path — multi-source query returns merged results
    Tool: Bash (python REPL)
    Preconditions: Neo4j has test concept nodes, Meilisearch has indexed content, PostgreSQL has embeddings
    Steps:
      1. python -c "from src.services.graphrag_query import GraphRAGQueryEngine; ..."
      2. Call engine.query('attention mechanism optimization', user_id='test-user-1', mode='hybrid')
      3. Assert len(results) >= 3
      4. Assert results[0].score > results[1].score (ranked order)
      5. Assert each result has .source field indicating which retrieval mode found it
    Expected Result: Merged, deduplicated, ranked results from all 3 sources
    Failure Indicators: Empty results, unsorted results, duplicate content IDs
    Evidence: .sisyphus/evidence/task-33-hybrid-query.json

  Scenario: Graceful degradation — Neo4j unavailable
    Tool: Bash (python REPL)
    Preconditions: Neo4j service stopped, Meilisearch and PostgreSQL running
    Steps:
      1. Call engine.query('attention mechanism', user_id='test-user-1', mode='hybrid')
      2. Assert no exception raised
      3. Assert results returned from text + semantic sources only
      4. Assert log contains warning about Neo4j unavailability
    Expected Result: Partial results from available backends, no crash
    Failure Indicators: Exception raised, empty results, no warning logged
    Evidence: .sisyphus/evidence/task-33-degradation.json
  ```

  **Commit**: YES
  - Message: `feat(graphrag): hybrid query engine with graph+text+semantic fusion`
  - Files: `src/services/graphrag_query.py`, `tests/unit/test_graphrag_query.py`
  - Pre-commit: `uv run pytest tests/unit/test_graphrag_query.py -v`

- [ ] 34. Feed View Page — Card List with Grid/List Toggle

  **What to do**:
  - Implement `frontend/src/app/feed/page.tsx` — main feed page showing content cards
  - Create `frontend/src/components/feed/ContentCard.tsx` — individual content card:
    - Card shows: AI summary (2-3 lines), source icon + name, content type badge (硬核知识/思想性/时效信息), push reason snippet, timestamp, match score indicator
    - Card actions: 👍 高质量 / ⏰ 稍后再看 / 📖 已知晓 / 👎 无价值 buttons
    - Clicking card navigates to detail page (`/content/[id]`)
  - Create `frontend/src/components/feed/FeedHeader.tsx` — header with:
    - Grid/List view toggle (icon buttons)
    - Sort dropdown: relevance / newest / oldest
    - Filter chips: content type, source, date range
    - Current user mode indicator (日常/项目攻关/探索)
  - Create `frontend/src/components/feed/FeedSkeleton.tsx` — loading skeleton
  - API integration: `GET /api/v1/feed?page=1&limit=20&sort=relevance&type=all`
  - Infinite scroll with `IntersectionObserver`
  - Empty state: illustration + “No content yet — add sources in Settings”
  - Responsive: 1-column mobile, 2-column tablet, 3-column desktop grid; single-column list
  - Reference Folo’s card layout patterns from `Folo/apps/desktop/layer/renderer/src/modules/entry-column/`
  - TDD: Component tests in `frontend/src/components/feed/__tests__/ContentCard.test.tsx`

  **Must NOT do**:
  - Do NOT implement real-time WebSocket updates yet (Phase 3)
  - Do NOT build advanced filtering UI — keep simple with dropdown + chips
  - Do NOT use state management library — React state + SWR/React Query for data fetching
  - Do NOT over-style — use Tailwind CSS with clean, minimal design

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: UI component development with responsive layout, card design, interaction patterns
  - **Skills**: [`frontend-ui-ux`]
    - `frontend-ui-ux`: Card layout design, responsive grid, visual hierarchy
  - **Skills Evaluated but Omitted**:
    - `playwright`: Testing done in Task 39

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2.1 (with Tasks 33, 35, 36)
  - **Blocks**: Task 39 (frontend tests)
  - **Blocked By**: Tasks 29 (Next.js scaffolding), 30 (layout shell)

  **References**:
  **Pattern References**:
  - `Folo/apps/desktop/layer/renderer/src/modules/entry-column/` — Card layout patterns, list/grid view
  - `Folo/packages/internal/components/ui/` — Reusable UI primitives (buttons, badges, skeletons)
  - `frontend/src/app/layout.tsx` — Next.js app shell from Task 30
  **API/Type References**:
  - `src/api/v1/content.py` — Feed API endpoint returning paginated content (Task 12)
  - `src/models/content.py:ContentResponse` — Response DTO shape for content cards
  **External References**:
  - DESIGN.md:938-942 — Core interaction constraints (every parsed content appears in card flow)
  - DESIGN.md:674-683 — Feedback types and their meaning (👍/⏰/📖/👎/❓/💬)
  **WHY Each Reference Matters**:
  - Folo card patterns: Copy visual structure and interaction model, not the code
  - DESIGN.md feedback types: Exactly which buttons to show and what each means

  **Acceptance Criteria**:
  **TDD:**
  - [ ] Test file: `frontend/src/components/feed/__tests__/ContentCard.test.tsx`
  - [ ] `cd frontend && npx vitest run src/components/feed` → PASS (5+ tests, 0 failures)

  **QA Scenarios:**
  ```
  Scenario: Happy path — feed page loads with content cards
    Tool: Playwright (playwright skill)
    Preconditions: Backend running with 5+ seeded content items, frontend at localhost:3000
    Steps:
      1. Navigate to http://localhost:3000/feed
      2. Wait for selector `.content-card` (timeout: 10s)
      3. Assert: at least 3 `.content-card` elements visible
      4. Assert: first card contains `.card-summary` with non-empty text
      5. Assert: first card contains `.card-source` badge
      6. Assert: first card has feedback buttons (`.btn-quality`, `.btn-later`, `.btn-known`, `.btn-worthless`)
      7. Take screenshot
    Expected Result: Feed page shows content cards with summary, source, feedback buttons
    Failure Indicators: Empty page, missing cards, missing feedback buttons
    Evidence: .sisyphus/evidence/task-34-feed-cards.png

  Scenario: Grid/List toggle changes layout
    Tool: Playwright (playwright skill)
    Preconditions: Feed page loaded with content
    Steps:
      1. Navigate to http://localhost:3000/feed
      2. Assert default layout is grid (`.feed-grid` class present)
      3. Click `.toggle-list` button
      4. Assert layout changes to list (`.feed-list` class present)
      5. Take screenshot of list view
    Expected Result: Layout toggles between grid and list
    Failure Indicators: Toggle not found, layout doesn't change
    Evidence: .sisyphus/evidence/task-34-list-toggle.png

  Scenario: Empty state when no content
    Tool: Playwright (playwright skill)
    Preconditions: Backend with empty database
    Steps:
      1. Navigate to http://localhost:3000/feed
      2. Wait for page load (timeout: 10s)
      3. Assert: `.empty-state` element visible
      4. Assert: text contains "No content" or "添加源"
    Expected Result: Friendly empty state message
    Failure Indicators: Blank page, error, stuck spinner
    Evidence: .sisyphus/evidence/task-34-empty-state.png
  ```

  **Commit**: YES
  - Message: `feat(frontend): feed page with content cards, grid/list toggle`
  - Files: `frontend/src/app/feed/page.tsx`, `frontend/src/components/feed/ContentCard.tsx`, `frontend/src/components/feed/FeedHeader.tsx`, `frontend/src/components/feed/FeedSkeleton.tsx`
  - Pre-commit: `cd frontend && npx vitest run src/components/feed`

- [ ] 35. Content Detail Page + Reading View

  **What to do**:
  - Implement `frontend/src/app/content/[id]/page.tsx` — content detail with three-panel layout:
    - **Panel 1 — AI Analysis**: AI summary, key takeaways, push reason, reading suggestion (精读/速览/只看某部分)
    - **Panel 2 — Content Subgraph**: Visual display of concept nodes and relationships (simple CSS+SVG node-link diagram, NOT full React Flow — that’s Phase 4 Task 53)
    - **Panel 3 — Original Content**: Full rendered content (Markdown/HTML), link to original source
  - Create `frontend/src/components/content/AIAnalysis.tsx` — AI analysis with structured sections
  - Create `frontend/src/components/content/ContentSubgraph.tsx` — simple graph:
    - Concept nodes as colored circles/pills with labels
    - Edges as lines with relationship labels
    - Highlight mastered concepts (green) vs unknown (gray) vs partial (yellow)
    - Use CSS + SVG, NOT a heavy graph library
  - Create `frontend/src/components/content/OriginalContent.tsx` — full content rendering:
    - Markdown rendering (react-markdown), code highlighting (rehype-highlight)
    - Image lazy loading, “Open original” link button
  - Create `frontend/src/components/content/FeedbackBar.tsx` — sticky bottom bar:
    - Same feedback buttons as cards (👍/⏰/📖/👎) plus ❓ “解释概念” and 💬 “追问”
    - Confirmation toast after feedback
  - API: `GET /api/v1/content/{id}` returns full content + AI analysis + subgraph
  - Responsive: mobile panels stack vertically; desktop side-by-side

  **Must NOT do**:
  - Do NOT implement React Flow graph visualization — use simple CSS+SVG (React Flow is Phase 4)
  - Do NOT implement QA dialog flow — just button placeholder (Task 52)
  - Do NOT implement “追问” free-form dialog — just button placeholder
  - Do NOT over-engineer panel resizing — simple CSS approach

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Multi-panel layout, content rendering, simple graph visualization
  - **Skills**: [`frontend-ui-ux`]
    - `frontend-ui-ux`: Three-panel layout, reading experience, graph visualization styling
  - **Skills Evaluated but Omitted**:
    - `playwright`: Testing in Task 39

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2.1 (with Tasks 33, 34, 36)
  - **Blocks**: Task 39 (frontend tests)
  - **Blocked By**: Tasks 29 (Next.js scaffolding), 30 (layout shell), 10 (AI analysis generation)

  **References**:
  **Pattern References**:
  - `Folo/apps/desktop/layer/renderer/src/modules/entry-content/` — Content detail view patterns
  - `frontend/src/components/feed/ContentCard.tsx` — Feedback button patterns to reuse (Task 34)
  **API/Type References**:
  - `src/models/content.py:ContentSubgraph` — Subgraph data structure (nodes + edges)
  - DESIGN.md:358-373 — Content subgraph generation and match scoring
  **External References**:
  - DESIGN.md:940-942 — Three core info blocks: content subgraph, AI analysis, original content
  - DESIGN.md:1027-1031 — Review push design: concept testing, linking, application prompts
  **WHY Each Reference Matters**:
  - Folo entry-content: Reading view layout patterns to follow
  - ContentSubgraph type: Exact shape of nodes/edges data for visualization
  - DESIGN.md three-block rule: Mandatory UI structure

  **Acceptance Criteria**:
  **TDD:**
  - [ ] Test file: `frontend/src/components/content/__tests__/ContentDetail.test.tsx`
  - [ ] `cd frontend && npx vitest run src/components/content` → PASS (5+ tests)

  **QA Scenarios:**
  ```
  Scenario: Happy path — content detail loads with three panels
    Tool: Playwright (playwright skill)
    Preconditions: Backend has content id='test-content-1', AI analysis generated, subgraph extracted
    Steps:
      1. Navigate to http://localhost:3000/content/test-content-1
      2. Wait for selector `.content-detail` (timeout: 10s)
      3. Assert `.ai-analysis` panel visible with non-empty summary text
      4. Assert `.content-subgraph` panel visible with at least 2 `.concept-node` elements
      5. Assert `.original-content` panel visible with rendered markdown
      6. Assert `.feedback-bar` sticky at bottom with 6 buttons
      7. Take screenshot
    Expected Result: All three panels rendered with real data, feedback bar visible
    Failure Indicators: Missing panels, empty content, broken graph, no feedback bar
    Evidence: .sisyphus/evidence/task-35-content-detail.png

  Scenario: Subgraph shows mastery colors
    Tool: Playwright (playwright skill)
    Preconditions: Content with subgraph where some concepts mastered, some not
    Steps:
      1. Navigate to content detail page
      2. Find `.concept-node` elements
      3. Assert at least one node has `.mastered` class (green)
      4. Assert at least one node has `.unknown` class (gray)
    Expected Result: Concept nodes colored by mastery level
    Failure Indicators: All nodes same color, missing mastery data
    Evidence: .sisyphus/evidence/task-35-subgraph-mastery.png
  ```

  **Commit**: YES
  - Message: `feat(frontend): content detail with AI analysis, subgraph, and reading view`
  - Files: `frontend/src/app/content/[id]/page.tsx`, `frontend/src/components/content/AIAnalysis.tsx`, `frontend/src/components/content/ContentSubgraph.tsx`, `frontend/src/components/content/OriginalContent.tsx`, `frontend/src/components/content/FeedbackBar.tsx`
  - Pre-commit: `cd frontend && npx vitest run src/components/content`

- [ ] 36. Settings Page — Sources, Preferences, Schedule

  **What to do**:
  - Implement `frontend/src/app/settings/page.tsx` — settings page with tabbed sections:
    - **Sources tab**: Content sources list (RSS/arXiv), add/remove/edit, test connection, status
    - **Preferences tab**: Content type weight sliders, ε slider (0.03-0.20), daily push limit, quiet hours
    - **Schedule tab**: Push schedule per time slot (morning/work/lunch/evening/late_night/weekend)
    - **Profile tab**: User mode selector (日常/项目攻关/探索/低能量), project description, reading time
  - Create `frontend/src/components/settings/SourceManager.tsx`, `PreferenceSliders.tsx`, `ScheduleEditor.tsx`, `UserModeSelector.tsx`
  - API: `GET/PUT /api/v1/settings`, `POST/DELETE /api/v1/sources`
  - Auto-save with debounce + toast
  - TDD: `frontend/src/components/settings/__tests__/Settings.test.tsx`

  **Must NOT do**:
  - Do NOT build connector-specific config (Phase 4)
  - Do NOT implement OAuth flows — RSS/arXiv only need URLs
  - Do NOT build Notion/Obsidian import — Phase 4

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Form-heavy UI with sliders, grids, tabs, auto-save
  - **Skills**: [`frontend-ui-ux`]
    - `frontend-ui-ux`: Form design, slider UX, visual schedule grid

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2.1 (with Tasks 33, 34, 35)
  - **Blocks**: Task 39
  - **Blocked By**: Task 30, Task 15, Task 24

  **References**:
  - `frontend/src/app/layout.tsx` — Navigation structure (Task 30)
  - `src/api/v1/sources.py` — Source CRUD (Task 15)
  - DESIGN.md:780-783 — ε presets (保守 0.03, 平衡 0.08, 探索 0.20)
  - DESIGN.md:797-835 — Push schedule YAML
  - DESIGN.md:375-396 — User state machine modes

  **Acceptance Criteria**:
  **TDD:** `cd frontend && npx vitest run src/components/settings` → PASS (5+ tests)
  **QA Scenarios:**
  ```
  Scenario: Add RSS source
    Tool: Playwright
    Steps:
      1. Navigate to http://localhost:3000/settings → Sources tab
      2. Click `.add-source`, fill `.source-url`="https://hnrss.org/best", `.source-name`="HN Best"
      3. Click `.save-source`
      4. Assert: source appears in `.source-list-item`
    Evidence: .sisyphus/evidence/task-36-add-source.png

  Scenario: Epsilon slider persists
    Tool: Playwright
    Steps:
      1. Preferences tab → set `.epsilon-slider` to 0.20
      2. Wait 1s (debounce) → reload page
      3. Assert: slider still at 0.20
    Evidence: .sisyphus/evidence/task-36-epsilon-slider.png
  ```

  **Commit**: YES
  - Message: `feat(frontend): settings page with sources, preferences, schedule`
  - Files: `frontend/src/app/settings/page.tsx`, `frontend/src/components/settings/*.tsx`
  - Pre-commit: `cd frontend && npx vitest run src/components/settings`

- [ ] 37. Knowledge Graph Update on User Feedback

  **What to do**:
  - Implement `src/services/kg_updater.py` — KG update triggered by feedback:
    - 👍: Extract concepts, update mastery, add edges
    - 📖: Confirm mastery → 1.0, reduce similar recommendations
    - 👎: LLM mismatch analysis, update source/topic weights
    - ❓: Record gap (mastery → 0.1), schedule prerequisites
    - Inferential: user understood B → prerequisite A auto-boosted
  - `KGUpdater` class with skill dispatch (DESIGN.md:685-732):
    - `update_on_feedback(user_id, content_id, feedback_type) -> KGUpdateResult`
    - Skills: `_update_knowledge_graph()`, `_adjust_preferences()`, `_calibrate_difficulty()`, `_discover_interest()`
  - Neo4j Cypher for mastery updates, Celery async task for background processing
  - TDD: `tests/unit/test_kg_updater.py` (10+ tests)

  **Must NOT do**:
  - Do NOT implement periodic_self_review — Phase 3
  - Do NOT modify content scoring during feedback

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Complex multi-path business logic with graph mutations
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (after Wave 2.1)
  - **Blocks**: Task 38
  - **Blocked By**: Tasks 24, 33, 28

  **References**:
  - `src/services/understanding.py` — LLM call patterns for structured extraction (Task 10)
  - `src/graph/client.py` — Cypher execution (Task 27)
  - DESIGN.md:674-683 — Feedback types table
  - DESIGN.md:685-732 — Skill system YAML
  - DESIGN.md:661-669 — KG auto-maintenance rules

  **Acceptance Criteria**:
  **TDD:** `uv run pytest tests/unit/test_kg_updater.py -v` → PASS (10+ tests)
  **QA Scenarios:**
  ```
  Scenario: Positive feedback boosts mastery
    Tool: Bash (python REPL)
    Preconditions: User KG with 'Attention' mastery=0.5
    Steps:
      1. Call kg_updater.update_on_feedback('test-1', 'ring-att-1', 'positive')
      2. Query Neo4j → Assert mastery > 0.5
    Evidence: .sisyphus/evidence/task-37-positive.json

  Scenario: Inferential boost
    Tool: Bash (python REPL)
    Preconditions: A(0.3) →prerequisite→ B(0.2)
    Steps:
      1. Positive feedback on content about B
      2. Assert A.mastery > 0.3
    Evidence: .sisyphus/evidence/task-37-inferential.json
  ```

  **Commit**: YES
  - Message: `feat(feedback): KG update with skill dispatch`
  - Files: `src/services/kg_updater.py`, `tests/unit/test_kg_updater.py`
  - Pre-commit: `uv run pytest tests/unit/test_kg_updater.py -v`

- [ ] 38. Phase 2 Integration Tests

  **What to do**:
  - `tests/integration/test_phase2_integration.py`:
    - Content-to-KG: ingest → subgraph → Neo4j → GraphRAG queryable
    - Feedback loop: feedback → KG update → query reflects changes
    - Push-to-Feed: scored → pushed → feed API → correct ordering
    - Match scoring: high-match ranks above low-match
  - `tests/integration/test_telegram_flow.py`:
    - Mock webhook → bot → correct response
    - Feedback callback → KG update → acknowledgment
  - Docker Compose test env (all services), 10 content items, 3 types, 1 user

  **Must NOT do**:
  - Do NOT test frontend (Task 39) or performance (Phase 4)
  - Do NOT mock databases — use real services

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: None
  - **Blocked By**: Tasks 33-37

  **References**:
  - `tests/integration/test_phase1_integration.py` — Patterns (Task 22)
  - `docker-compose.test.yml` — Test env (Task 3)

  **Acceptance Criteria**:
  **TDD:** `uv run pytest tests/integration/ -v --timeout=120` → PASS (15+ tests)
  **QA Scenarios:**
  ```
  Scenario: Full pipeline
    Tool: Bash (pytest)
    Steps: uv run pytest tests/integration/test_phase2_integration.py -v
    Expected: 15+ tests pass
    Evidence: .sisyphus/evidence/task-38-integration.txt

  Scenario: Feedback affects queries
    Tool: Bash (pytest)
    Steps: uv run pytest tests/integration/test_phase2_integration.py::test_feedback_loop -v
    Expected: Ranking changes after feedback
    Evidence: .sisyphus/evidence/task-38-feedback-loop.txt
  ```

  **Commit**: YES
  - Message: `test(phase2): integration tests for pipeline, feedback, Telegram`
  - Files: `tests/integration/test_phase2_*.py`, `tests/integration/test_telegram_flow.py`
  - Pre-commit: `uv run pytest tests/integration/ -v --timeout=120`

- [ ] 39. Frontend Tests — Vitest + Playwright E2E

  **What to do**:
  - Vitest unit tests for all Phase 2 components:
    - `frontend/src/components/feed/__tests__/FeedPage.test.tsx`
    - `frontend/src/components/content/__tests__/ContentDetail.test.tsx`
    - `frontend/src/components/settings/__tests__/SettingsPage.test.tsx`
  - Playwright E2E in `frontend/e2e/`:
    - `feed.spec.ts`, `settings.spec.ts`, `navigation.spec.ts`
  - `frontend/playwright.config.ts` targeting localhost:3000
  - Seeded backend data (same fixtures as Task 38)

  **Must NOT do**:
  - Do NOT test backend logic, do NOT use hardcoded waits, do NOT test visual regression

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: [`playwright`]

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: None
  - **Blocked By**: Tasks 34, 35, 36

  **References**:
  - All Phase 2 frontend components (Tasks 34-36)
  - Playwright + Vitest docs for test patterns

  **Acceptance Criteria**:
  **TDD:**
  - [ ] `npx vitest run` → PASS (15+ component tests)
  - [ ] `cd frontend && npx playwright test` → PASS (6+ E2E tests)
  **QA Scenarios:**
  ```
  Scenario: Vitest pass
    Tool: Bash
    Steps: cd frontend && npx vitest run --reporter=verbose
    Expected: exit 0, 15+ passed
    Evidence: .sisyphus/evidence/task-39-vitest.txt

  Scenario: Playwright E2E pass
    Tool: Bash
    Steps: cd frontend && npx playwright test --reporter=list
    Expected: exit 0, 6+ passed
    Evidence: .sisyphus/evidence/task-39-playwright.txt
  ```

  **Commit**: YES
  - Message: `test(frontend): vitest + Playwright E2E for Phase 2`
  - Files: `frontend/src/components/**/__tests__/*.test.tsx`, `frontend/e2e/*.spec.ts`
  - Pre-commit: `cd frontend && npx vitest run && npx playwright test`

---

### Phase 3 — Cognitive System

#### Wave 3.1 — Memory + Repetition + State

- [ ] 40. FSRS Spaced Repetition Engine

  **What to do**:
  - Implement `src/services/fsrs_engine.py` — Free Spaced Repetition Scheduler (FSRS v5) algorithm:
    - Core formula: R(t) = e^(-t/S) where R = retention, t = elapsed time, S = stability
    - Default intervals: 1d → 3d → 7d → 14d → 30d → 90d
    - Parameters: desired_retention (default 0.9), w[] weight vector (17 params)
    - `FSRSEngine` class with:
      - `schedule_review(card: ReviewCard) -> ReviewSchedule` — compute next optimal review time
      - `record_review(card_id: str, rating: Rating) -> UpdatedCard` — update stability/difficulty after review
      - `get_due_cards(user_id: str, limit: int) -> list[ReviewCard]` — fetch cards due for review
    - Rating enum: Again (1), Hard (2), Good (3), Easy (4)
    - State machine: New → Learning → Review → Relearning
  - DB model: `src/models/review_card.py` — ReviewCard with stability, difficulty, due_date, state, reps, lapses
  - Review types from DESIGN.md:1027-1031:
    - Concept test: “Do you remember X?” (question first, then reveal)
    - Link new knowledge: “You learned X before, here’s a related new finding”
    - Application prompt: “Your project Y — could method Z help?”
  - Celery Beat scheduled task: check due cards daily, push reviews via Telegram
  - TDD: `tests/unit/test_fsrs_engine.py` (12+ tests)

  **Must NOT do**:
  - Do NOT implement full Anki compatibility — only FSRS v5 core algorithm
  - Do NOT build review UI yet — reviews pushed via Telegram only
  - Do NOT store raw content for review — store concept references + review prompts

  **Recommended Agent Profile**:
  - **Category**: `ultrabrain`
    - Reason: Mathematical algorithm (exponential decay, stability updates) with state machine
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3.1 (with Tasks 41, 42, 44, 45)
  - **Blocks**: Task 48 (Phase 3 tests), Task 57 (Telegram reminders)
  - **Blocked By**: Task 2 (DB schema/models), Task 15 (Celery Beat scheduling)

  **References**:
  - DESIGN.md:1013-1037 — Spaced repetition section: formula, intervals, adaptive adjustment
  - DESIGN.md:1027-1031 — Three review push types (concept test, link new, application prompt)
  - `src/services/celery_tasks.py` — Celery task patterns (Task 15)
  - Open source: `py-fsrs` library for reference implementation (MIT license)

  **Acceptance Criteria**:
  **TDD:** `uv run pytest tests/unit/test_fsrs_engine.py -v` → PASS (12+ tests)
  **QA Scenarios:**
  ```
  Scenario: Schedule review after positive rating
    Tool: Bash (python REPL)
    Steps:
      1. Create ReviewCard(stability=1.0, difficulty=5.0, state='Review')
      2. Call fsrs.record_review(card_id, rating=Rating.Good)
      3. Assert: card.stability > 1.0 (increased)
      4. Assert: card.due_date > now + 1 day
    Expected: Stability increases, next review scheduled further out
    Evidence: .sisyphus/evidence/task-40-fsrs-schedule.json

  Scenario: Card lapses back to relearning
    Tool: Bash (python REPL)
    Steps:
      1. Card in Review state, call record_review(rating=Rating.Again)
      2. Assert: card.state == 'Relearning'
      3. Assert: card.lapses incremented
      4. Assert: card.stability decreased
    Expected: Failed review puts card into relearning with shorter interval
    Evidence: .sisyphus/evidence/task-40-fsrs-lapse.json
  ```

  **Commit**: YES
  - Message: `feat(fsrs): spaced repetition engine with FSRS v5 algorithm`
  - Files: `src/services/fsrs_engine.py`, `src/models/review_card.py`, `tests/unit/test_fsrs_engine.py`
  - Pre-commit: `uv run pytest tests/unit/test_fsrs_engine.py -v`

- [ ] 41. 3-Tier Memory System (Working / Short-term / Long-term)

  **What to do**:
  - Implement `src/services/memory_system.py` — three-layer memory per DESIGN.md:307-320:
    - **Working Memory**: Small capacity, real-time updates, current project/weekly focus
      - User can declare: “I’m researching MoE load balancing”
      - System can auto-infer from reading behavior
      - Directly affects push ranking weight (×3 for related content)
      - Archived when task/project completes
    - **Short-term Memory**: Medium capacity, daily updates, recent 2-week reading drift
      - Tracks topic frequency shifts over 14-day sliding window
      - Decays: 2 weeks without touch → fades
    - **Long-term Memory**: Large capacity, slow updates, internalized core knowledge
      - Stable cognitive frameworks, mastered fundamentals
      - Very slow decay, requires spaced repetition to maintain
  - `MemoryManager` class:
    - `update_working_memory(user_id, declaration: str | None, auto_infer: bool)`
    - `update_short_term(user_id)` — called daily by Celery Beat
    - `promote_to_long_term(user_id, concept_id)` — when mastery stable > 30 days
    - `get_memory_context(user_id) -> MemoryContext` — unified context for push scoring
    - `decay_short_term(user_id)` — run weekly, fade untouched short-term items
  - PostgreSQL storage: `user_memories` table with layer, content, weight, last_touched, created_at
  - Integration with push scorer: MemoryContext feeds into R_relevance calculation
  - TDD: `tests/unit/test_memory_system.py` (10+ tests)

  **Must NOT do**:
  - Do NOT use external memory frameworks (MemGPT/Letta) — custom implementation
  - Do NOT auto-infer working memory from single reading — require pattern (3+ related in 48h)
  - Do NOT expose memory internals to user directly — only through dashboard (Task 47)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Multi-layer state management with decay logic and inference
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3.1 (with Tasks 40, 42, 44, 45)
  - **Blocks**: Task 48
  - **Blocked By**: Task 2 (DB schema/models), Task 20 (push ranker uses memory context)

  **References**:
  - DESIGN.md:307-320 — Memory tier definitions, capacity, update frequency, decay
  - DESIGN.md:317-320 — Working memory special design (declaration + auto-infer)
  - `src/services/push_scorer.py` — R_relevance formula integration point (Task 31)

  **Acceptance Criteria**:
  **TDD:** `uv run pytest tests/unit/test_memory_system.py -v` → PASS (10+ tests)
  **QA Scenarios:**
  ```
  Scenario: Working memory declaration boosts related content
    Tool: Bash (python REPL)
    Steps:
      1. Call memory.update_working_memory('user-1', declaration='Researching MoE load balancing')
      2. Get memory_context = memory.get_memory_context('user-1')
      3. Assert: 'MoE' in memory_context.working_topics
      4. Assert: memory_context.working_weight_boost > 1.0
    Expected: Working memory captured and boosts active
    Evidence: .sisyphus/evidence/task-41-working-memory.json

  Scenario: Short-term decays after 14 days
    Tool: Bash (python REPL)
    Steps:
      1. Insert short-term memory item with last_touched = 15 days ago
      2. Call memory.decay_short_term('user-1')
      3. Assert: item weight reduced or removed
    Expected: Untouched items fade after 2 weeks
    Evidence: .sisyphus/evidence/task-41-decay.json
  ```

  **Commit**: YES
  - Message: `feat(memory): 3-tier memory system with working/short/long-term layers`
  - Files: `src/services/memory_system.py`, `src/models/user_memory.py`, `tests/unit/test_memory_system.py`
  - Pre-commit: `uv run pytest tests/unit/test_memory_system.py -v`

- [ ] 42. User State Machine (日常/项目攻关/探索/低能量)

  **What to do**:
  - Implement `src/services/user_state.py` — user mode state machine per DESIGN.md:375-396:
    - **日常模式 (Daily)**: Default, balanced content mix, normal scheduling
    - **项目攻关模式 (Project)**: R_relevance ×3 for project topics, non-related content paused, real-time priority up
    - **探索模式 (Explore)**: Cross-domain content ratio increased, depth over timeliness, weekend/user-triggered
    - **低能量模式 (Low Energy)**: Only lightweight timely content, hard-core paused, late night/user-marked
  - State transitions:
    - Daily → Project: user declares project (Telegram /project command)
    - Daily → Explore: weekend auto or /explore command
    - Daily → Low Energy: late night auto or /rest command
    - Project → Daily: user declares project complete or /daily command
    - Any → Daily: explicit /daily reset
  - `UserStateManager` class:
    - `get_state(user_id) -> UserMode`
    - `transition(user_id, target: UserMode, context: dict) -> TransitionResult`
    - `get_push_modifiers(user_id) -> PushModifiers` — weight multipliers for push scorer
    - `auto_detect_mode(user_id, current_time: datetime) -> UserMode | None` — time-based auto transitions
  - Celery Beat: hourly check for auto-transitions (late night, weekend)
  - War mode (Project) effects per DESIGN.md:847-856:
    - Data sources: add temporary keywords/RSS for project topic
    - Ranker: ×3 relevance for project content
    - Scheduler: non-related non-urgent content paused
    - Exit: generate project knowledge summary report
  - TDD: `tests/unit/test_user_state.py` (8+ tests)

  **Must NOT do**:
  - Do NOT auto-transition to Project mode — always requires user declaration
  - Do NOT persist mode across sessions if user hasn’t interacted in 7+ days — reset to Daily

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: State machine with complex transition rules and side effects
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3.1 (with Tasks 40, 41, 44, 45)
  - **Blocks**: Task 48
  - **Blocked By**: Task 14 (Telegram bot commands), Task 20 (push ranker)

  **References**:
  - DESIGN.md:375-396 — State machine diagram with all modes and transitions
  - DESIGN.md:847-856 — War mode (Project) detailed effects
  - `src/services/push_scorer.py` — Where push modifiers are consumed (Task 31)
  - `src/bot/handlers.py` — Telegram command handlers (Task 28)

  **Acceptance Criteria**:
  **TDD:** `uv run pytest tests/unit/test_user_state.py -v` → PASS (8+ tests)
  **QA Scenarios:**
  ```
  Scenario: Enter Project mode boosts related content
    Tool: Bash (python REPL)
    Steps:
      1. Call state_mgr.transition('user-1', UserMode.PROJECT, {'topic': 'CUDA kernel optimization'})
      2. Get modifiers = state_mgr.get_push_modifiers('user-1')
      3. Assert: modifiers.relevance_multiplier == 3.0
      4. Assert: modifiers.pause_non_related == True
    Expected: Project mode active with correct push modifiers
    Evidence: .sisyphus/evidence/task-42-project-mode.json

  Scenario: Auto-detect Low Energy at night
    Tool: Bash (python REPL)
    Steps:
      1. Call state_mgr.auto_detect_mode('user-1', datetime(2026, 3, 1, 23, 30))
      2. Assert: returns UserMode.LOW_ENERGY
    Expected: Late night auto-detected
    Evidence: .sisyphus/evidence/task-42-auto-detect.json
  ```

  **Commit**: YES
  - Message: `feat(state): user mode state machine with 4 modes and auto-transitions`
  - Files: `src/services/user_state.py`, `tests/unit/test_user_state.py`
  - Pre-commit: `uv run pytest tests/unit/test_user_state.py -v`

#### Wave 3.2 — Reports + Dashboard + Integration

- [ ] 43. Auto Weekly Report Generation

  **What to do**:
  - Implement `src/services/report_generator.py` — automatic weekly/monthly reports per DESIGN.md:963-1001:
    - **Weekly report structure** (DESIGN.md:969-991):
      - Learning overview: X items read (N 硬核 + M 思想性 + K 时效), KG changes
      - Core takeaways: synthesize 2-3 theme clusters from the week’s readings (LLM-generated)
      - KG changes: new concepts, mastery updates, discovered gaps
      - Next week recommendations: based on learning trajectory
    - **Topic aggregation report** (DESIGN.md:993-1001): when user has 5+ positive-rated items on same topic, generate deep synthesis
  - `ReportGenerator` class:
    - `generate_weekly(user_id, week_start, week_end) -> Report`
    - `generate_topic_report(user_id, topic: str) -> Report`
    - `render_markdown(report: Report) -> str`
    - `render_pdf(report: Report) -> bytes` — using `weasyprint` or `markdown-pdf`
  - LLM integration: DeepSeek API for synthesis (via LLMClient), Jinja2 templates for report structure
  - Celery Beat: weekly cron (Sunday 20:00) triggers generation, sends via Telegram + stores in DB
  - Telegram push: send report summary + PDF attachment
  - TDD: `tests/unit/test_report_generator.py` (8+ tests)

  **Must NOT do**:
  - Do NOT generate reports for weeks with < 3 read items — skip with “not enough data”
  - Do NOT use complex LaTeX — Markdown to PDF via weasyprint is sufficient
  - Do NOT generate topic reports automatically — only when 5+ threshold met, prompt user first

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: LLM-driven content synthesis, template rendering, multi-format output
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3.2 (with Tasks 46, 47)
  - **Blocks**: Task 48
  - **Blocked By**: Tasks 37 (KG updates provide data), 40 (FSRS provides review stats), 41 (memory provides context)

  **References**:
  - DESIGN.md:963-1001 — Report structure, weekly report example, topic aggregation
  - `src/llm/deepseek.py` — LLM client implementation for synthesis calls (Task 4)
  - `prompts/` directory — Jinja2 templates (Task 10)

  **Acceptance Criteria**:
  **TDD:** `uv run pytest tests/unit/test_report_generator.py -v` → PASS (8+ tests)
  **QA Scenarios:**
  ```
  Scenario: Weekly report generated with correct structure
    Tool: Bash (python REPL)
    Preconditions: User read 8 items in past week, gave feedback on 5
    Steps:
      1. Call report_gen.generate_weekly('user-1', week_start, week_end)
      2. Assert: report.overview.total_read == 8
      3. Assert: report.takeaways is not empty (LLM generated)
      4. Assert: report.kg_changes has new concepts listed
      5. Call report_gen.render_markdown(report) → assert valid markdown
    Expected: Structured report with real data
    Evidence: .sisyphus/evidence/task-43-weekly-report.md

  Scenario: PDF rendering works
    Tool: Bash
    Steps:
      1. pdf_bytes = report_gen.render_pdf(report)
      2. Assert: len(pdf_bytes) > 1000
      3. Write to file, verify PDF header (%PDF-)
    Expected: Valid PDF generated
    Evidence: .sisyphus/evidence/task-43-report.pdf
  ```

  **Commit**: YES
  - Message: `feat(reports): auto weekly report generation with LLM synthesis + PDF`
  - Files: `src/services/report_generator.py`, `tests/unit/test_report_generator.py`, `prompts/weekly_report.j2`
  - Pre-commit: `uv run pytest tests/unit/test_report_generator.py -v`

- [ ] 44. Advanced Feedback Skill System

  **What to do**:
  - Implement `src/services/skill_executor.py` — formalize the skill system from DESIGN.md:685-732:
    - Skill registry: YAML-based skill definitions loaded at startup
    - `SkillExecutor` class:
      - `execute(skill_name: str, context: SkillContext) -> SkillResult`
      - `get_triggered_skills(feedback_type: FeedbackType) -> list[Skill]`
    - Skills from DESIGN.md:
      - `update_knowledge_graph`: trigger on positive_feedback/learned_new
      - `adjust_preferences`: trigger on negative_feedback/already_known
      - `calibrate_difficulty`: trigger on too_hard/too_easy/explain_concept
      - `discover_interest`: trigger on explore_new_topic/positive_on_unexpected
      - `periodic_self_review`: trigger on weekly_cron — NEW in Phase 3
    - Periodic self-review skill (weekly):
      - Review feedback statistics, detect preference drift
      - Identify knowledge gaps from pattern analysis
      - Generate user model diff report (what changed this week)
  - Load skill definitions from `config/skills.yaml` (YAML → Pydantic models)
  - Integrate with existing `KGUpdater` (Task 37) — refactor to use SkillExecutor as dispatcher
  - TDD: `tests/unit/test_skill_executor.py` (8+ tests)

  **Must NOT do**:
  - Do NOT rewrite KGUpdater from scratch — refactor to use SkillExecutor as dispatcher
  - Do NOT build a generic plugin system — skills are predefined, not user-extensible

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: System design with registry pattern, refactoring existing code
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3.1 (with Tasks 40, 41, 42, 45)
  - **Blocks**: Task 48
  - **Blocked By**: Task 37 (KGUpdater to refactor)

  **References**:
  - DESIGN.md:685-732 — Complete Skill system YAML definitions
  - `src/services/kg_updater.py` — Existing update logic to refactor (Task 37)

  **Acceptance Criteria**:
  **TDD:** `uv run pytest tests/unit/test_skill_executor.py -v` → PASS (8+ tests)
  **QA Scenarios:**
  ```
  Scenario: Skill dispatch on feedback
    Tool: Bash (python REPL)
    Steps:
      1. Load skills from config/skills.yaml
      2. Call executor.get_triggered_skills(FeedbackType.POSITIVE)
      3. Assert: returns ['update_knowledge_graph'] skill
      4. Call executor.execute('update_knowledge_graph', context)
      5. Assert: KG mastery updated (delegates to KGUpdater)
    Expected: Correct skill dispatched and executed
    Evidence: .sisyphus/evidence/task-44-skill-dispatch.json

  Scenario: Periodic self-review runs
    Tool: Bash (python REPL)
    Steps:
      1. Call executor.execute('periodic_self_review', weekly_context)
      2. Assert: diff report generated with preference_drift and knowledge_gaps
    Expected: Self-review produces actionable diff report
    Evidence: .sisyphus/evidence/task-44-self-review.json
  ```

  **Commit**: YES
  - Message: `feat(skills): advanced feedback skill system with registry and periodic review`
  - Files: `src/services/skill_executor.py`, `config/skills.yaml`, `tests/unit/test_skill_executor.py`
  - Pre-commit: `uv run pytest tests/unit/test_skill_executor.py -v`

- [ ] 45. Leiden Community Detection (NetworkX + leidenalg)

  **What to do**:
  - Implement `src/services/community_detection.py` — knowledge graph community detection:
    - Export user KG subgraph from Neo4j into NetworkX graph
    - Run Leiden algorithm via `leidenalg` library (Python-side, NOT Neo4j GDS)
    - Detect concept communities (clusters of related knowledge)
    - Store community labels back in Neo4j as node properties
    - Use communities for:
      - Cross-domain bridge detection (nodes connecting different communities)
      - Knowledge gap identification (sparse communities)
      - Exploration recommendations (adjacent communities user hasn’t explored)
  - `CommunityDetector` class:
    - `detect_communities(user_id) -> list[Community]`
    - `find_bridges(user_id) -> list[BridgeConcept]` — concepts connecting 2+ communities
    - `find_sparse_communities(user_id) -> list[Community]` — under-explored areas
    - `update_community_labels(user_id, communities)` — write back to Neo4j
  - Celery Beat: run weekly (after weekly report), results feed into exploration strategy
  - NetworkX + igraph + leidenalg for algorithm; Neo4j for storage
  - TDD: `tests/unit/test_community_detection.py` (6+ tests)

  **Must NOT do**:
  - Do NOT use Neo4j GDS — Enterprise only! Use Python-side leidenalg (Metis directive)
  - Do NOT run on every feedback event — weekly batch only
  - Do NOT expose raw community data to user — only through KG visualization (Task 53)

  **Recommended Agent Profile**:
  - **Category**: `ultrabrain`
    - Reason: Graph algorithm implementation with community detection theory
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3.1 (with Tasks 40, 41, 42, 44)
  - **Blocks**: Task 48
  - **Blocked By**: Task 27 (Neo4j schema), Task 37 (KG has data)

  **References**:
  - `src/graph/client.py` — Export graph data (Task 27)
  - DESIGN.md:771-775 — Cross-domain bridge pushing and neighborhood exploration
  - `leidenalg` docs: RBConfigurationVertexPartition, resolution parameter

  **Acceptance Criteria**:
  **TDD:** `uv run pytest tests/unit/test_community_detection.py -v` → PASS (6+ tests)
  **QA Scenarios:**
  ```
  Scenario: Detect communities in test KG
    Tool: Bash (python REPL)
    Preconditions: Neo4j with 20+ concept nodes, 30+ edges forming 3 clear clusters
    Steps:
      1. Call detector.detect_communities('user-1')
      2. Assert: 3 communities detected
      3. Assert: each community has coherent concepts (e.g., ML cluster, Systems cluster)
    Expected: Meaningful community structure detected
    Evidence: .sisyphus/evidence/task-45-communities.json

  Scenario: Find bridge concepts
    Tool: Bash (python REPL)
    Steps:
      1. Call detector.find_bridges('user-1')
      2. Assert: at least 1 bridge concept found (connects 2+ communities)
    Expected: Cross-domain bridge concepts identified
    Evidence: .sisyphus/evidence/task-45-bridges.json
  ```

  **Commit**: YES
  - Message: `feat(graph): Leiden community detection with bridge and gap analysis`
  - Files: `src/services/community_detection.py`, `tests/unit/test_community_detection.py`
  - Pre-commit: `uv run pytest tests/unit/test_community_detection.py -v`

- [ ] 46. Report UI Page + PDF Export

  **What to do**:
  - Implement `frontend/src/app/reports/page.tsx` — report listing page:
    - List of generated reports (weekly + topic), sorted by date
    - Each report card shows: title, date range, summary excerpt, content count
    - Click to view full report in rendered Markdown
  - Implement `frontend/src/app/reports/[id]/page.tsx` — report detail page:
    - Full rendered Markdown report with sections
    - KG changes visualization (simple before/after diff)
    - “Download PDF” button (calls backend endpoint)
    - “Share” button (copy link)
  - Create `frontend/src/components/reports/ReportCard.tsx`, `ReportViewer.tsx`
  - API: `GET /api/v1/reports`, `GET /api/v1/reports/{id}`, `GET /api/v1/reports/{id}/pdf`
  - TDD: Component tests

  **Must NOT do**:
  - Do NOT generate PDF client-side — use backend PDF generation (Task 43)
  - Do NOT build report editing — reports are read-only generated content

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3.2 (with Tasks 43, 47)
  - **Blocks**: Task 48
  - **Blocked By**: Task 43 (reports must exist), Task 29 (Next.js foundation)

  **References**:
  - DESIGN.md:963-1001 — Report structure and content
  - `frontend/src/components/feed/ContentCard.tsx` — Card layout patterns (Task 34)

  **Acceptance Criteria**:
  **TDD:** `cd frontend && npx vitest run src/components/reports` → PASS (4+ tests)
  **QA Scenarios:**
  ```
  Scenario: View weekly report
    Tool: Playwright
    Preconditions: Backend has generated weekly report
    Steps:
      1. Navigate to http://localhost:3000/reports
      2. Assert: at least 1 `.report-card` visible
      3. Click first report card
      4. Assert: `.report-viewer` shows rendered markdown
      5. Assert: `.download-pdf` button visible
    Evidence: .sisyphus/evidence/task-46-report-view.png
  ```

  **Commit**: YES
  - Message: `feat(frontend): report listing and viewer with PDF download`
  - Files: `frontend/src/app/reports/page.tsx`, `frontend/src/app/reports/[id]/page.tsx`, `frontend/src/components/reports/*.tsx`
  - Pre-commit: `cd frontend && npx vitest run src/components/reports`

- [ ] 47. Cognitive Dashboard — Learning Progress

  **What to do**:
  - Implement `frontend/src/app/dashboard/page.tsx` — cognitive dashboard showing:
    - **Learning velocity**: items read/week trend chart (line chart, last 8 weeks)
    - **Knowledge growth**: KG node count over time, new vs mastered
    - **Memory tiers**: visual breakdown of working/short-term/long-term items
    - **Community map**: simplified KG cluster view (communities from Task 45 as colored groups)
    - **Review schedule**: upcoming FSRS due cards count, streak info
    - **Mode indicator**: current user mode with recent mode history
  - Use lightweight chart library: `recharts` or `chart.js` via react-chartjs-2
  - Create `frontend/src/components/dashboard/LearningVelocity.tsx`, `KnowledgeGrowth.tsx`, `MemoryOverview.tsx`, `CommunityOverview.tsx`, `ReviewSchedule.tsx`
  - API: `GET /api/v1/dashboard/stats` — aggregated endpoint returning all dashboard data
  - Responsive: cards in 2-column grid on desktop, stack on mobile
  - TDD: Component tests for each widget

  **Must NOT do**:
  - Do NOT build interactive KG visualization — that’s Task 53 (React Flow)
  - Do NOT use D3.js directly — use React-friendly wrappers
  - Do NOT over-animate — simple, clean data display

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3.2 (with Tasks 43, 46)
  - **Blocks**: Task 48
  - **Blocked By**: Tasks 40 (FSRS data), 41 (memory data), 45 (community data), 26 (Next.js)

  **References**:
  - DESIGN.md:1003-1009 — Learning trajectory visualization (KG evolution, Sankey, gap analysis)
  - `src/services/memory_system.py` — Memory tier data (Task 41)
  - `src/services/community_detection.py` — Community data (Task 45)
  - `src/services/fsrs_engine.py` — Review schedule data (Task 40)

  **Acceptance Criteria**:
  **TDD:** `cd frontend && npx vitest run src/components/dashboard` → PASS (5+ tests)
  **QA Scenarios:**
  ```
  Scenario: Dashboard loads with all widgets
    Tool: Playwright
    Preconditions: Backend with user activity data (8+ weeks)
    Steps:
      1. Navigate to http://localhost:3000/dashboard
      2. Assert: `.learning-velocity` chart visible
      3. Assert: `.knowledge-growth` chart visible
      4. Assert: `.memory-overview` with 3 tier indicators
      5. Assert: `.review-schedule` with due count
    Expected: All dashboard widgets render with data
    Evidence: .sisyphus/evidence/task-47-dashboard.png
  ```

  **Commit**: YES
  - Message: `feat(frontend): cognitive dashboard with learning metrics and charts`
  - Files: `frontend/src/app/dashboard/page.tsx`, `frontend/src/components/dashboard/*.tsx`
  - Pre-commit: `cd frontend && npx vitest run src/components/dashboard`

- [ ] 48. Phase 3 Integration Tests

  **What to do**:
  - `tests/integration/test_phase3_integration.py`:
    - FSRS flow: content marked positive → review card created → due date computed → review pushed
    - Memory flow: reading pattern → short-term updated → decay over time → promotion to long-term
    - State machine: mode transitions → push modifiers change → feed ordering changes
    - Report generation: week of activity → weekly report → correct structure + PDF
    - Community detection: KG with data → communities detected → bridges identified
    - Skill system: feedback → correct skills triggered → KG + preferences updated
  - Frontend E2E additions:
    - `frontend/e2e/dashboard.spec.ts` — dashboard widgets load
    - `frontend/e2e/reports.spec.ts` — view report, download PDF
  - Docker Compose test env with all services

  **Must NOT do**:
  - Do NOT test Phase 4 features
  - Do NOT mock core services — integration tests use real backends

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: [`playwright`]

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: None
  - **Blocked By**: Tasks 40-47

  **References**:
  - `tests/integration/test_phase2_integration.py` — Integration patterns (Task 38)
  - All Phase 3 task descriptions for flow specifications

  **Acceptance Criteria**:
  **TDD:**
  - [ ] `uv run pytest tests/integration/test_phase3_integration.py -v` → PASS (12+ tests)
  - [ ] `cd frontend && npx playwright test e2e/dashboard.spec.ts e2e/reports.spec.ts` → PASS (4+ tests)
  **QA Scenarios:**
  ```
  Scenario: FSRS + memory + state integration
    Tool: Bash (pytest)
    Steps: uv run pytest tests/integration/test_phase3_integration.py -v --timeout=180
    Expected: 12+ integration tests pass
    Evidence: .sisyphus/evidence/task-48-integration.txt

  Scenario: Dashboard + reports E2E
    Tool: Bash
    Steps: cd frontend && npx playwright test e2e/dashboard.spec.ts e2e/reports.spec.ts
    Expected: 4+ E2E tests pass
    Evidence: .sisyphus/evidence/task-48-frontend-e2e.txt
  ```

  **Commit**: YES
  - Message: `test(phase3): integration tests for FSRS, memory, state, reports, communities`
  - Files: `tests/integration/test_phase3_integration.py`, `frontend/e2e/dashboard.spec.ts`, `frontend/e2e/reports.spec.ts`
  - Pre-commit: `uv run pytest tests/integration/test_phase3_integration.py -v && cd frontend && npx playwright test`

### Phase 4 — Full Vision

#### Wave 4.1 — Connector Expansion + Exploration (Tasks 49-52)

- [ ] 49. Connector Framework v2 + Batch 1 Connectors (X, Reddit, GitHub Stars, YouTube, Hacker News)

  **What to do**:
  - Refactor the connector base class from Phase 0 (Task 7) into a v2 framework with:
    - Standardized `ConnectorConfig` model: name, schedule (cron), rate_limit, retry_policy, auth_type
    - Plugin discovery: connectors register via `@register_connector("x")` decorator
    - Unified error handling: `ConnectorError` hierarchy (AuthError, RateLimitError, ParseError, NetworkError)
    - Health check endpoint per connector: `GET /api/connectors/{name}/health`
    - Metrics: items_fetched, errors, latency per connector (stored in PostgreSQL)
  - Implement 5 connectors:
    - **X (Twitter)**: Use Nitter RSS bridge or official API v2 (user timeline, list, search). Extract tweets + threads. Handle media (images→alt text, videos→skip). Rate limit: 300 req/15min (API) or 1 req/5s (Nitter)
    - **Reddit**: Use PRAW or Reddit JSON API (`.json` suffix). Fetch from configured subreddits + saved posts. Extract self-text + top comments. Handle crosspost/link posts. Rate limit: 60 req/min
    - **GitHub Stars**: Use GitHub REST API. Fetch starred repos, release notes (latest 3), README changes. Extract changelogs via `/releases` endpoint. Rate limit: 5000 req/hr (authenticated)
    - **YouTube**: Use `yt-dlp` for metadata + `youtube-transcript-api` for captions. Fall back to Whisper transcription for high-value channels without captions. Store transcript as content body
    - **Hacker News**: Use Algolia HN API (`hn.algolia.com/api/v1`). Fetch front page + `best` stories. Extract top 5 comments per story. Rate limit: 10000 req/hr
  - Each connector must have: unit tests (mock HTTP), integration test (real API with `@pytest.mark.integration`)
  - Add `GET /api/connectors` list endpoint and `POST /api/connectors/{name}/trigger` manual trigger
  - Add connector management Celery tasks: `schedule_connector_fetch`, `check_connector_health`

  **Must NOT do**:
  - Do NOT implement paid API access for X — use free tier or Nitter bridge
  - Do NOT implement video download or storage — transcript/metadata only for YouTube
  - Do NOT implement OAuth flows in this task — use API keys/tokens from environment
  - Do NOT implement the Chinese platform connectors (Task 50)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Multiple external API integrations requiring careful error handling and rate limiting
  - **Skills**: [`playwright`]
    - `playwright`: Needed for QA scenarios testing connector health endpoints and admin UI
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: No frontend work in this task

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 51, 52)
  - **Parallel Group**: Wave 4.1
  - **Blocks**: Task 50 (needs framework v2), Task 55 (admin panel needs connector list), Task 58 (final E2E)
  - **Blocked By**: Task 7 (existing connector base), Task 13 (Phase 0 pipeline), Task 27 (Neo4j integration)

  **References**:

  **Pattern References** (existing code to follow):
  - `src/connectors/base.py` — Current connector base class from Task 7, extend this
  - `src/connectors/rss.py` — RSS connector pattern (fetch→parse→normalize), replicate for new connectors
  - `src/connectors/arxiv.py` — arXiv connector pattern, similar structure for API-based connectors
  - `src/services/pipeline.py` — Pipeline service that connectors feed into

  **API/Type References**:
  - `src/models/content.py:RawContent` — The model all connectors must produce
  - `src/schemas/connector.py` — Connector config schema (create/extend)

  **External References**:
  - X API v2 docs: https://developer.x.com/en/docs/x-api
  - PRAW (Reddit): https://praw.readthedocs.io/en/stable/
  - GitHub REST API: https://docs.github.com/en/rest
  - youtube-transcript-api: https://github.com/jdepoix/youtube-transcript-api
  - HN Algolia API: https://hn.algolia.com/api
  - Nitter instances: https://github.com/zedeus/nitter/wiki/Instances

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `tests/unit/connectors/test_connector_framework.py` — Plugin discovery, config validation, error hierarchy (8+ tests)
  - [ ] `tests/unit/connectors/test_x_connector.py` — Mock X API responses (5+ tests)
  - [ ] `tests/unit/connectors/test_reddit_connector.py` — Mock Reddit JSON (5+ tests)
  - [ ] `tests/unit/connectors/test_github_connector.py` — Mock GitHub API (5+ tests)
  - [ ] `tests/unit/connectors/test_youtube_connector.py` — Mock yt-dlp + transcripts (5+ tests)
  - [ ] `tests/unit/connectors/test_hn_connector.py` — Mock HN Algolia (5+ tests)
  - [ ] `uv run pytest tests/unit/connectors/ -v` → PASS (33+ tests, 0 failures)

  **QA Scenarios:**

  ```
  Scenario: Connector list endpoint returns all registered connectors
    Tool: Bash (curl)
    Preconditions: API running, all 5 new + 2 existing connectors registered
    Steps:
      1. curl -s http://localhost:8000/api/connectors | uv run python -m json.tool
      2. Assert response is JSON array with length >= 7
      3. Assert each item has fields: name, status, last_fetch, item_count, error_count
      4. Assert "x", "reddit", "github_stars", "youtube", "hackernews" all present in names
    Expected Result: 200 OK, 7+ connectors listed with correct schema
    Failure Indicators: Missing connector names, 500 error, schema validation failure
    Evidence: .sisyphus/evidence/task-49-connector-list.json

  Scenario: Manual trigger fetches items from HN connector
    Tool: Bash (curl)
    Preconditions: API running, HN connector configured
    Steps:
      1. curl -s -X POST http://localhost:8000/api/connectors/hackernews/trigger
      2. Wait 10s for Celery task completion
      3. curl -s http://localhost:8000/api/connectors/hackernews/health
      4. Assert health response shows last_fetch within last 30s and items_fetched > 0
    Expected Result: Trigger returns 202, health shows successful fetch
    Failure Indicators: Trigger returns 500, health shows error state, items_fetched = 0
    Evidence: .sisyphus/evidence/task-49-hn-trigger.json

  Scenario: Connector error handling — invalid API key
    Tool: Bash (curl)
    Preconditions: X connector configured with invalid API key
    Steps:
      1. curl -s -X POST http://localhost:8000/api/connectors/x/trigger
      2. Wait 5s
      3. curl -s http://localhost:8000/api/connectors/x/health
      4. Assert health shows status="error", last_error contains "AuthError"
    Expected Result: Connector gracefully handles auth failure, reports error in health
    Failure Indicators: Unhandled exception, 500 on health endpoint, no error info
    Evidence: .sisyphus/evidence/task-49-connector-auth-error.json
  ```

  **Commit**: YES
  - Message: `feat(connectors): add connector framework v2 with X, Reddit, GitHub, YouTube, HN connectors`
  - Files: `src/connectors/`, `src/schemas/connector.py`, `tests/unit/connectors/`
  - Pre-commit: `uv run pytest tests/unit/connectors/ -v`

- [ ] 50. Connector Batch 2 — Chinese Platforms + Podcast (微信公众号, 知乎, 小红书, Bilibili, Podcast RSS)

  **What to do**:
  - Implement 5 additional connectors using the v2 framework from Task 49:
    - **微信公众号 (WeChat Official Accounts)**: Use `wechatarticles` library or RSS bridges (WeRSS/wechat2rss). Extract article HTML→markdown via trafilatura. Handle image-heavy articles. Note: Official API requires verified business account — use RSS bridge approach
    - **知乎 (Zhihu)**: Use Zhihu RSS feeds (zhihu.com/api/v4) or RSS bridge. Fetch from followed topics + specific users. Extract answers with markdown formatting. Handle LaTeX formulas (preserve as-is)
    - **小红书 (Xiaohongshu/RED)**: Use reverse-engineered API or web scraping via Playwright. Extract note text + image descriptions (OCR or alt text). This is the hardest connector — implement as best-effort with graceful degradation
    - **Bilibili**: Use `bilibili-api-python` library. Fetch from followed users + hot videos in configured categories. Extract via subtitle API or Whisper transcription. Store transcript as content
    - **Podcast RSS**: Standard RSS connector variant. Use `feedparser` for RSS + `yt-dlp` for audio download + Whisper (local via faster-whisper) for transcription. Store transcript + episode metadata. Support Apple Podcasts and Spotify RSS feeds
  - Each connector: unit tests (mocked) + integration marker
  - Handle Chinese text encoding (UTF-8) consistently across all connectors
  - Add connector-specific configuration schema extensions

  **Must NOT do**:
  - Do NOT attempt to crack WeChat's encryption or use unofficial login — RSS bridge only
  - Do NOT store raw audio files permanently — transcribe then delete audio
  - Do NOT implement user authentication flows for Chinese platforms
  - Do NOT spend more than basic effort on 小红书 if anti-scraping is too aggressive — mark as experimental

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Complex web scraping and API integration with Chinese platforms requiring nuanced error handling
  - **Skills**: []
    - No special skills needed — pure backend work
  - **Skills Evaluated but Omitted**:
    - `playwright`: Only needed if Xiaohongshu requires browser automation, but that should be encapsulated in the connector itself

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 49 framework)
  - **Parallel Group**: Wave 4.1 (starts after Task 49 completes, parallel with 51, 52)
  - **Blocks**: Task 55 (admin panel), Task 58 (final E2E)
  - **Blocked By**: Task 49 (connector framework v2 must exist first)

  **References**:

  **Pattern References**:
  - `src/connectors/base.py` — Connector v2 base class (from Task 49)
  - `src/connectors/rss.py` — RSS pattern, reuse for podcast connector
  - `src/connectors/youtube.py` — YouTube transcript pattern (from Task 49), similar for Bilibili

  **External References**:
  - bilibili-api-python: https://github.com/Nemo2011/bilibili-api
  - faster-whisper: https://github.com/SYSTRAN/faster-whisper
  - wechat2rss: https://github.com/ttttmr/wechat2rss
  - feedparser: https://feedparser.readthedocs.io/

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `tests/unit/connectors/test_wechat_connector.py` — Mock RSS bridge responses (4+ tests)
  - [ ] `tests/unit/connectors/test_zhihu_connector.py` — Mock Zhihu API (4+ tests)
  - [ ] `tests/unit/connectors/test_xiaohongshu_connector.py` — Mock responses, test graceful degradation (3+ tests)
  - [ ] `tests/unit/connectors/test_bilibili_connector.py` — Mock API + transcript (4+ tests)
  - [ ] `tests/unit/connectors/test_podcast_connector.py` — Mock RSS + Whisper transcription (5+ tests)
  - [ ] `uv run pytest tests/unit/connectors/test_{wechat,zhihu,xiaohongshu,bilibili,podcast}_connector.py -v` → PASS (20+ tests, 0 failures)

  **QA Scenarios:**

  ```
  Scenario: All 12 connectors visible and configurable
    Tool: Bash (curl)
    Preconditions: API running with all connectors registered
    Steps:
      1. curl -s http://localhost:8000/api/connectors | uv run python -m json.tool
      2. Assert response contains 12 connectors (rss, arxiv, x, reddit, github_stars, youtube, hackernews, wechat, zhihu, xiaohongshu, bilibili, podcast)
      3. For each: assert has name, status, config_schema fields
    Expected Result: 200 OK, 12 connectors listed
    Failure Indicators: Count < 12, missing Chinese platform connectors
    Evidence: .sisyphus/evidence/task-50-all-connectors.json

  Scenario: Podcast connector transcribes audio episode
    Tool: Bash (curl + check)
    Preconditions: A test podcast RSS feed configured, Whisper model available
    Steps:
      1. curl -s -X POST http://localhost:8000/api/connectors/podcast/trigger -H 'Content-Type: application/json' -d '{"feed_url": "https://feeds.simplecast.com/54nAGcIl", "max_episodes": 1}'
      2. Wait 60s (transcription takes time)
      3. Query latest content: curl -s 'http://localhost:8000/api/content?source=podcast&limit=1'
      4. Assert content has non-empty body with transcript text (length > 500 chars)
    Expected Result: Episode fetched, transcribed, stored with transcript body
    Failure Indicators: Empty body, transcription error, timeout > 120s
    Evidence: .sisyphus/evidence/task-50-podcast-transcript.json

  Scenario: Graceful degradation — Xiaohongshu anti-scraping
    Tool: Bash (curl)
    Preconditions: Xiaohongshu connector configured
    Steps:
      1. curl -s -X POST http://localhost:8000/api/connectors/xiaohongshu/trigger
      2. Wait 10s
      3. curl -s http://localhost:8000/api/connectors/xiaohongshu/health
      4. Assert status is either "ok" (if fetch worked) or "degraded" (if blocked), NOT "error"
    Expected Result: Connector handles anti-scraping gracefully with degraded status
    Failure Indicators: Unhandled exception, crash, status="error" without recovery info
    Evidence: .sisyphus/evidence/task-50-xiaohongshu-degraded.json
  ```

  **Commit**: YES
  - Message: `feat(connectors): add WeChat, Zhihu, Xiaohongshu, Bilibili, Podcast connectors`
  - Files: `src/connectors/`, `tests/unit/connectors/`
  - Pre-commit: `uv run pytest tests/unit/connectors/ -v`

- [ ] 51. ε-Greedy Exploration Mechanism + Cross-Domain Bridging

  **What to do**:
  - Implement the exploration vs exploitation mechanism in the push ranker (DESIGN.md:754-789):
    - Core: With probability ε (default 0.08), replace a ranked item with a random high-quality item from outside user's usual domains
    - Store ε as user-configurable setting: 🐌 Conservative (0.03), 🚶 Balanced (0.08), 🚀 Explore (0.20)
    - Quality floor: exploration items must still pass `Q_total > 0.7` threshold
    - Tag exploration pushes with `is_exploration=True` in push record
    - Track exploration feedback separately: `exploration_positive_rate`, `exploration_discovery_rate`
  - Implement cross-domain bridging (DESIGN.md:771-778):
    - Detect when two knowledge graph clusters share a non-obvious connection (via shared concepts with low user mastery)
    - Generate bridge explanations via LLM: "You know X well. This content connects X to Y in an unexpected way."
    - Use Jinja2 prompt template: `prompts/exploration_bridge.j2`
  - Implement cognitive boundary expansion:
    - Query KG for nodes exactly 1 hop outside user's mastered area (mastery < 0.3 but adjacent to mastery > 0.7)
    - These become candidates for the exploration pool
  - Add Telegram commands:
    - `/explore` — manually trigger a batch of 3 exploration pushes
    - `/explore_mode <conservative|balanced|explore>` — set ε level
  - Add exploration analytics to `/stats` output

  **Must NOT do**:
  - Do NOT implement the full "Serendipity Engine" (DESIGN.md:777) — that's a research project, not an engineering task
  - Do NOT change the core ranking formula — only add the ε-sampling layer on top
  - Do NOT push exploration content during "war mode" (project focus mode)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Requires understanding of probabilistic ranking, KG graph traversal, and careful integration with existing ranker without breaking it
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `playwright`: No UI work in this task

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 49, 52)
  - **Parallel Group**: Wave 4.1
  - **Blocks**: Task 55 (admin panel shows exploration stats), Task 58 (final E2E)
  - **Blocked By**: Task 20 (push ranker), Task 27 (Neo4j KG for graph traversal), Task 45 (community detection for cross-domain identification)

  **References**:

  **Pattern References**:
  - `src/services/ranker.py` — Push ranker from Task 20, add ε-sampling layer here
  - `src/services/kg_service.py` — KG service from Task 27, use for neighbor queries
  - `src/services/community.py` — Community detection from Task 45, use for cross-domain identification
  - `src/bot/handlers/commands.py` — Existing bot commands, add `/explore` and `/explore_mode`

  **API/Type References**:
  - `src/models/push.py:PushRecord` — Add `is_exploration` boolean field
  - `src/models/user.py:UserPreferences` — Add `exploration_epsilon` field

  **External References**:
  - DESIGN.md:754-789 — ε-greedy exploration strategy specification
  - DESIGN.md:771-778 — Cross-domain bridging and cognitive boundary expansion

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `tests/unit/test_exploration.py` — ε-sampling logic, quality floor, exploration pool selection (8+ tests)
  - [ ] `tests/unit/test_bridge_detection.py` — Cross-domain bridge detection from KG (5+ tests)
  - [ ] `tests/unit/test_exploration_commands.py` — Telegram /explore and /explore_mode (4+ tests)
  - [ ] `uv run pytest tests/unit/test_exploration*.py tests/unit/test_bridge*.py -v` → PASS (17+ tests)

  **QA Scenarios:**

  ```
  Scenario: Exploration items appear in push batch with ε=0.20
    Tool: Bash (curl)
    Preconditions: API running, user has exploration_epsilon=0.20, 50+ content items in DB across multiple domains
    Steps:
      1. Generate 20 push batches: for i in $(seq 1 20); do curl -s http://localhost:8000/api/push/generate?user_id=test_user >> /tmp/push_batches.json; done
      2. Parse all push items, count those with is_exploration=true
      3. Calculate exploration_rate = exploration_count / total_items
      4. Assert exploration_rate is between 0.10 and 0.35 (statistical range around 0.20)
    Expected Result: ~20% of pushes are exploration items
    Failure Indicators: exploration_rate < 0.05 or > 0.40, no is_exploration field
    Evidence: .sisyphus/evidence/task-51-exploration-rate.json

  Scenario: Exploration items respect quality floor
    Tool: Bash (curl)
    Preconditions: API running, mixed quality content in DB (some Q_total < 0.7)
    Steps:
      1. curl -s http://localhost:8000/api/push/generate?user_id=test_user&force_explore=true
      2. For each returned exploration item, fetch its quality score
      3. Assert ALL exploration items have Q_total >= 0.7
    Expected Result: No low-quality items sneak through exploration
    Failure Indicators: Any exploration item with Q_total < 0.7
    Evidence: .sisyphus/evidence/task-51-quality-floor.json

  Scenario: /explore command returns cross-domain content via Telegram
    Tool: interactive_bash (tmux)
    Preconditions: Bot running, test user has established KG with mastered domains
    Steps:
      1. Send /explore command to bot
      2. Wait 10s for response
      3. Assert bot returns 3 content cards
      4. Assert each card has "🌍" exploration tag and bridge explanation
    Expected Result: 3 exploration cards with cross-domain explanations
    Failure Indicators: No response, fewer than 3 cards, missing bridge explanation
    Evidence: .sisyphus/evidence/task-51-explore-command.txt
  ```

  **Commit**: YES
  - Message: `feat(exploration): implement ε-greedy exploration with cross-domain bridging`
  - Files: `src/services/exploration.py`, `src/services/ranker.py`, `src/bot/handlers/`, `prompts/exploration_bridge.j2`, `tests/unit/test_exploration*.py`
  - Pre-commit: `uv run pytest tests/unit/test_exploration*.py tests/unit/test_bridge*.py -v`

- [ ] 52. "Explain Concept" QA Dialog Flow + Free-form Follow-up

  **What to do**:
  - Implement the "❓ Explain Concept" feedback action (DESIGN.md:682, 879-885):
    - When user taps "❓ Explain Concept" on a push card:
      1. System extracts key concepts from the pushed content (via LLM or pre-extracted from content_subgraph)
      2. Present concept selector as inline keyboard buttons (max 5 concepts)
      3. User selects a concept
      4. System generates personalized explanation using user's KG:
       - Find concepts user already knows (mastery > 0.7) that relate to selected concept
       - Build explanation that bridges from known → unknown via analogy/derivation
       - Use Jinja2 template: `prompts/explain_concept.j2`
      5. After explanation, offer: "Did this help?" (👍 Yes / 👎 No / 💬 Tell me more)
      6. If "Yes": update KG mastery for the concept (increment by 0.1-0.2)
      7. If "No": try alternative explanation strategy (different analogy, simpler terms)
      8. If "Tell me more": enter free-form QA dialog mode
  - Implement free-form follow-up dialog (💬 action from DESIGN.md:683):
    - After any push card, user can tap "💬 Follow up" to start a multi-turn conversation
    - Context includes: original content summary, content_subgraph, user's KG neighborhood
    - Conversation stored in `dialog_sessions` table with foreign key to push_record
    - Auto-close dialog after 10 minutes of inactivity
    - Extract insights from dialog to update user profile/KG
  - Add dialog session management:
    - `POST /api/dialog/start` — start from push_record_id
    - `POST /api/dialog/{session_id}/message` — send user message, get AI response
    - `GET /api/dialog/{session_id}` — get full dialog history
  - Create DB models: `DialogSession`, `DialogMessage`
  - LLM integration: use DeepSeek API with system prompt including user KG context

  **Must NOT do**:
  - Do NOT implement voice messages or audio input
  - Do NOT implement dialog memory beyond the single session (no cross-session dialog memory)
  - Do NOT allow dialog to modify content quality scores — only user KG mastery
  - Do NOT implement streaming responses in Telegram (send complete messages)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Complex multi-turn dialog state management with KG integration and LLM orchestration
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `playwright`: No browser UI in this task, Telegram-only

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 49, 51)
  - **Parallel Group**: Wave 4.1
  - **Blocks**: Task 55 (admin shows dialog stats), Task 58 (final E2E)
  - **Blocked By**: Task 14 (Telegram feedback handler), Task 27 (KG service for concept lookup), Task 28 (content subgraph for concept extraction)

  **References**:

  **Pattern References**:
  - `src/bot/handlers/feedback.py` — Existing feedback handlers from Task 14, extend with explain/follow-up
  - `src/llm/protocol.py` — LLM client protocol from Task 4, use for dialog responses
  - `src/services/kg_service.py` — KG queries for user mastery and concept neighborhoods
  - `prompts/` — Existing Jinja2 templates, follow same pattern

  **API/Type References**:
  - `src/models/push.py:PushRecord` — Foreign key for dialog sessions
  - `src/models/content.py:ContentSubgraph` — Source of extractable concepts
  - DESIGN.md:879-885 — Concept selector UX flow specification
  - DESIGN.md:682 — Feedback table row for "❓ Explain Concept"

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `tests/unit/test_concept_explain.py` — Concept extraction, explanation generation, mastery update (8+ tests)
  - [ ] `tests/unit/test_dialog_session.py` — Session lifecycle, message storage, auto-close (6+ tests)
  - [ ] `tests/unit/test_dialog_api.py` — API endpoints for dialog start/message/history (5+ tests)
  - [ ] `uv run pytest tests/unit/test_concept*.py tests/unit/test_dialog*.py -v` → PASS (19+ tests)

  **QA Scenarios:**

  ```
  Scenario: Full explain-concept flow via Telegram
    Tool: interactive_bash (tmux)
    Preconditions: Bot running, test user has KG with mastered concepts, a push with content_subgraph containing "Ring Attention"
    Steps:
      1. Tap "❓ Explain Concept" on a push card in Telegram
      2. Wait 3s, assert bot presents inline keyboard with concept buttons
      3. Tap "Ring Attention" concept button
      4. Wait 10s for LLM response
      5. Assert response contains: explanation text (>200 chars), reference to user's known concepts, analogy
      6. Assert "Did this help?" buttons appear (👍 / 👎 / 💬)
      7. Tap "👍 Yes"
      8. Verify KG mastery for "Ring Attention" increased via API: curl -s http://localhost:8000/api/kg/concept/ring-attention/mastery
    Expected Result: Personalized explanation delivered, mastery updated on positive feedback
    Failure Indicators: No concept buttons, generic explanation without personalization, mastery unchanged
    Evidence: .sisyphus/evidence/task-52-explain-flow.txt

  Scenario: Free-form follow-up dialog session
    Tool: Bash (curl)
    Preconditions: API running, dialog session started from a push
    Steps:
      1. curl -s -X POST http://localhost:8000/api/dialog/start -H 'Content-Type: application/json' -d '{"push_record_id": 1, "user_id": "test_user"}'
      2. Extract session_id from response
      3. curl -s -X POST http://localhost:8000/api/dialog/{session_id}/message -d '{"text": "How does this relate to FlashAttention?"}'
      4. Assert response has non-empty ai_response field (>100 chars)
      5. curl -s http://localhost:8000/api/dialog/{session_id}
      6. Assert dialog history has 2 messages (1 user + 1 assistant)
    Expected Result: Multi-turn dialog works with context-aware responses
    Failure Indicators: Empty response, session not found, context not included
    Evidence: .sisyphus/evidence/task-52-dialog-session.json

  Scenario: Dialog auto-close after inactivity
    Tool: Bash (curl + sleep)
    Preconditions: Active dialog session, auto-close configured to 10s for testing
    Steps:
      1. Start dialog session
      2. Send one message, get response
      3. Wait 15s (beyond auto-close threshold)
      4. curl -s http://localhost:8000/api/dialog/{session_id}
      5. Assert session status is "closed" with reason "inactivity"
    Expected Result: Session auto-closed after timeout
    Failure Indicators: Session still "active" after timeout
    Evidence: .sisyphus/evidence/task-52-dialog-autoclose.json
  ```

  **Commit**: YES
  - Message: `feat(dialog): implement concept explanation QA and free-form follow-up dialog`
  - Files: `src/services/dialog.py`, `src/services/concept_explain.py`, `src/models/dialog.py`, `src/api/dialog.py`, `src/bot/handlers/feedback.py`, `prompts/explain_concept.j2`, `tests/unit/test_concept*.py`, `tests/unit/test_dialog*.py`
  - Pre-commit: `uv run pytest tests/unit/test_concept*.py tests/unit/test_dialog*.py -v`

#### Wave 4.2 — Frontend Advanced + Export (Tasks 53-55)

- [ ] 53. Knowledge Graph Interactive Visualization (React Flow)

  **What to do**:
  - Build the interactive KG visualization page in the Next.js dashboard (DESIGN.md:899-904):
    - Use `reactflow` (React Flow) library for graph rendering:
      - Nodes = concepts, colored by type (concept/method/tool/theory) and sized by mastery level
      - Edges = relationships, labeled with relation type (prerequisite, extends, relates_to)
      - Node tooltip: concept name, mastery score, last updated, related content count
      - Click node: expand sidebar with concept details, linked content list, mastery history
    - Implement graph controls:
      - Zoom in/out, pan, fit-to-screen
      - Filter by: domain/community, mastery range (slider), concept type
      - Search: type-ahead search to locate and center on a concept node
      - Layout: force-directed (default), hierarchical, radial options
    - Knowledge mastery heatmap overlay:
      - Toggle heatmap mode: green (mastered) → yellow (learning) → red (unknown)
      - Opacity reflects mastery: high mastery = solid, low mastery = transparent
    - Knowledge gap analysis panel:
      - Show clusters of low-mastery nodes adjacent to high-mastery areas
      - Suggest "Next concepts to learn" based on graph neighborhood
    - Graph editing capabilities (DESIGN.md:904):
      - Edit node: rename concept, adjust mastery manually, merge duplicates
      - Edit edge: add/remove/retype relationships
      - Bulk operations: select multiple nodes, batch-update mastery
    - API integration:
      - `GET /api/kg/graph?user_id={id}&depth={n}&center={concept}` — fetch subgraph
      - `GET /api/kg/communities` — fetch community list with node counts
      - `PATCH /api/kg/node/{id}` — update mastery, rename
      - `POST /api/kg/edge` / `DELETE /api/kg/edge/{id}` — manage edges
  - Backend API endpoints for graph data (if not already from Phase 2):
    - Return graph in React Flow compatible format: `{nodes: [{id, data, position}], edges: [{id, source, target, label}]}`
    - Support pagination for large graphs (>500 nodes): return top N by relevance + connected subgraph

  **Must NOT do**:
  - Do NOT use D3.js directly — use React Flow for React integration
  - Do NOT implement 3D graph visualization — 2D only
  - Do NOT implement real-time collaborative editing
  - Do NOT pre-compute all graph layouts server-side — let React Flow handle layout client-side

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Complex interactive data visualization with React Flow, requires strong frontend skills and visual design sense
  - **Skills**: [`frontend-ui-ux`, `playwright`]
    - `frontend-ui-ux`: Graph visualization UI requires careful UX design for complex data
    - `playwright`: Needed for QA scenarios testing graph interactions
  - **Skills Evaluated but Omitted**:
    - `dev-browser`: Playwright skill sufficient for testing

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 54, 55)
  - **Parallel Group**: Wave 4.2
  - **Blocks**: Task 58 (final E2E)
  - **Blocked By**: Task 30 (Next.js dashboard shell), Task 27 (Neo4j KG service), Task 45 (community detection)

  **References**:

  **Pattern References**:
  - `frontend/src/app/dashboard/` — Existing dashboard layout from Task 38
  - `frontend/src/components/` — Existing shadcn/ui components
  - Folo reference: `Folo/packages/internal/components/ui/` — Component patterns for reference

  **API/Type References**:
  - `src/api/kg.py` — KG API endpoints from Task 27
  - `src/schemas/kg.py` — Graph node/edge schemas
  - DESIGN.md:899-904 — Knowledge graph page information architecture

  **External References**:
  - React Flow docs: https://reactflow.dev/docs/getting-started/introduction
  - React Flow examples: https://reactflow.dev/docs/examples/overview/

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `frontend/src/__tests__/components/KnowledgeGraph.test.tsx` — Graph rendering, filtering, search (6+ tests)
  - [ ] `frontend/src/__tests__/components/GraphControls.test.tsx` — Zoom, layout toggle, filter (4+ tests)
  - [ ] `frontend/src/__tests__/components/GraphEditor.test.tsx` — Node edit, edge management (4+ tests)
  - [ ] `cd frontend && npx vitest run src/__tests__/components/KnowledgeGraph* src/__tests__/components/Graph*` → PASS (14+ tests)

  **QA Scenarios:**

  ```
  Scenario: Graph loads and displays user's knowledge graph
    Tool: Playwright
    Preconditions: Dashboard running at localhost:3000, user logged in, KG has 20+ concepts with edges
    Steps:
      1. Navigate to http://localhost:3000/dashboard/knowledge-graph
      2. Wait for graph to render (selector: .react-flow__renderer)
      3. Count visible nodes: document.querySelectorAll('.react-flow__node').length
      4. Assert node count >= 15 (some may be off-screen)
      5. Assert edges visible: document.querySelectorAll('.react-flow__edge').length > 0
      6. Hover over a node, assert tooltip appears with concept name and mastery score
    Expected Result: Interactive graph with 20+ nodes, edges, tooltips
    Failure Indicators: Empty graph, no nodes, console errors, tooltip missing
    Evidence: .sisyphus/evidence/task-53-graph-loaded.png

  Scenario: Mastery heatmap overlay toggle
    Tool: Playwright
    Preconditions: Graph page loaded with nodes
    Steps:
      1. Click heatmap toggle button (selector: button[data-testid="heatmap-toggle"])
      2. Wait 1s for color transition
      3. Assert nodes have color classes applied (green/yellow/red based on mastery)
      4. Take screenshot showing heatmap colors
      5. Click toggle again to disable, assert colors revert to type-based
    Expected Result: Heatmap mode colors nodes by mastery, toggles cleanly
    Failure Indicators: No color change, all same color, toggle doesn't revert
    Evidence: .sisyphus/evidence/task-53-heatmap-toggle.png

  Scenario: Edit concept mastery via graph UI
    Tool: Playwright
    Preconditions: Graph loaded, node for "Attention Mechanism" visible
    Steps:
      1. Click on "Attention Mechanism" node
      2. Assert sidebar opens with concept details
      3. Find mastery slider (selector: input[data-testid="mastery-slider"])
      4. Set slider to 0.9
      5. Click "Save" button
      6. Wait 2s, verify API call succeeded
      7. Reload page, click same node, assert mastery shows 0.9
    Expected Result: Mastery updated via UI, persisted across reload
    Failure Indicators: Slider missing, save fails, mastery reverts on reload
    Evidence: .sisyphus/evidence/task-53-edit-mastery.png
  ```

  **Commit**: YES
  - Message: `feat(frontend): add interactive knowledge graph visualization with React Flow`
  - Files: `frontend/src/app/dashboard/knowledge-graph/`, `frontend/src/components/graph/`, `frontend/src/__tests__/components/`
  - Pre-commit: `cd frontend && npx vitest run && npx playwright test`

- [ ] 54. Content Export — Markdown + PDF Generation

  **What to do**:
  - Implement content export system (DESIGN.md:912-916, 993-1001):
    - **Single content export**: Export any content item as clean Markdown
      - Include: AI summary, key concepts, original content (cleaned), content subgraph as mermaid diagram
      - Template: `templates/export_single.md.j2`
    - **Topic aggregation export** (DESIGN.md:993-1001):
      - When user has 5+ positive-feedback items on same topic cluster, offer aggregation
      - LLM generates: topic overview, knowledge timeline, consensus/controversy points, open questions
      - Template: `templates/export_topic.md.j2`
    - **Weekly/Monthly report export** (DESIGN.md:963-991):
      - Auto-generated reports already exist from Task 43 — this task adds Markdown + PDF export
      - Reports available at: `GET /api/reports/{report_id}/export?format=md|pdf`
    - **PDF generation**: Use `weasyprint` or `markdown-pdf` to convert Markdown→PDF
      - Include: table of contents, page numbers, Alice branding header
      - Support: CJK characters (Chinese content), LaTeX formulas (via KaTeX CSS), code blocks with syntax highlighting
    - **Bulk export**: `POST /api/export/bulk` — export multiple items as zip archive
    - **Frontend integration**:
      - Export button on content detail page (Markdown icon + PDF icon)
      - Export button on weekly report page
      - "Export topic" suggestion card when 5+ items accumulated on a topic
    - **Telegram integration**: `/export <topic>` command sends PDF via Telegram document message

  **Must NOT do**:
  - Do NOT implement Notion/Obsidian sync in this task — that's a separate integration concern
  - Do NOT implement real-time collaborative editing of exports
  - Do NOT implement DOCX or EPUB formats — Markdown + PDF only

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Mix of backend (PDF generation, LLM aggregation) and frontend (export buttons), but not primarily visual
  - **Skills**: [`playwright`]
    - `playwright`: Testing export download in browser
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: Export buttons are simple UI additions, not complex design work

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 53, 55)
  - **Parallel Group**: Wave 4.2
  - **Blocks**: Task 58 (final E2E)
  - **Blocked By**: Task 30 (dashboard shell for frontend buttons), Task 43 (report generation for report export), Task 28 (content subgraph for mermaid diagrams)

  **References**:

  **Pattern References**:
  - `src/services/report.py` — Report generation from Task 43, extend with export formats
  - `prompts/` — Existing Jinja2 templates, follow same pattern for export templates
  - `frontend/src/components/content/ContentCard.tsx` — Add export buttons to existing card component

  **API/Type References**:
  - `src/models/content.py:Content` — Content model with subgraph data
  - `src/models/report.py:Report` — Report model from Task 43
  - DESIGN.md:912-916 — Library page with export functionality
  - DESIGN.md:993-1001 — Topic aggregation report specification

  **External References**:
  - weasyprint: https://doc.courtbouillon.org/weasyprint/stable/
  - python-markdown: https://python-markdown.github.io/

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `tests/unit/test_export.py` — Markdown generation, PDF conversion, bulk export (8+ tests)
  - [ ] `tests/unit/test_topic_aggregation.py` — Topic clustering, LLM aggregation (5+ tests)
  - [ ] `frontend/src/__tests__/components/ExportButton.test.tsx` — Export button rendering (3+ tests)
  - [ ] `uv run pytest tests/unit/test_export*.py tests/unit/test_topic*.py -v` → PASS (13+ tests)

  **QA Scenarios:**

  ```
  Scenario: Export single content as PDF
    Tool: Bash (curl)
    Preconditions: API running, content item with ID=1 exists with subgraph
    Steps:
      1. curl -s -o /tmp/export.pdf http://localhost:8000/api/content/1/export?format=pdf
      2. Assert file exists and size > 1KB: stat -f%z /tmp/export.pdf
      3. Assert PDF is valid: file /tmp/export.pdf | grep -q 'PDF'
      4. Use pdftotext to verify content: pdftotext /tmp/export.pdf - | head -20
      5. Assert output contains AI summary text from the content
    Expected Result: Valid PDF with AI summary, concepts, and formatted content
    Failure Indicators: Empty file, invalid PDF, missing content sections
    Evidence: .sisyphus/evidence/task-54-single-export.pdf

  Scenario: Topic aggregation report for 5+ liked items
    Tool: Bash (curl)
    Preconditions: User has given positive feedback on 6 items about "Attention Mechanisms"
    Steps:
      1. curl -s http://localhost:8000/api/export/topic-suggestions?user_id=test_user
      2. Assert response contains topic "Attention Mechanisms" with item_count >= 5
      3. curl -s -X POST http://localhost:8000/api/export/topic -d '{"topic": "Attention Mechanisms", "format": "md"}'
      4. Assert response is valid Markdown with sections: Overview, Timeline, Consensus, Open Questions
      5. Assert Markdown length > 2000 chars
    Expected Result: Aggregated Markdown report synthesizing 6 items
    Failure Indicators: Empty report, missing sections, no topic suggestions
    Evidence: .sisyphus/evidence/task-54-topic-aggregation.md

  Scenario: Export button works in dashboard
    Tool: Playwright
    Preconditions: Dashboard running, content detail page accessible
    Steps:
      1. Navigate to http://localhost:3000/dashboard/content/1
      2. Click export dropdown (selector: button[data-testid="export-menu"])
      3. Click "Download PDF" option
      4. Wait for download event, assert file downloaded with .pdf extension
    Expected Result: PDF file downloaded via browser
    Failure Indicators: No download, download error, empty file
    Evidence: .sisyphus/evidence/task-54-export-button.png
  ```

  **Commit**: YES
  - Message: `feat(export): add Markdown and PDF export for content, topics, and reports`
  - Files: `src/services/export.py`, `src/api/export.py`, `templates/export_*.md.j2`, `frontend/src/components/content/ExportButton.tsx`, `tests/`
  - Pre-commit: `uv run pytest tests/unit/test_export*.py tests/unit/test_topic*.py -v && npx vitest run`

- [ ] 55. Admin Panel + Analytics Dashboard

  **What to do**:
  - Build the admin/management section of the web dashboard (DESIGN.md:925-935):
    - **Connector Management** (DESIGN.md:926):
      - Table view: all connectors with status (running/stopped/error), last fetch time, item count, error count, fetch frequency
      - Actions: start/stop, trigger manual fetch, edit config (cron schedule, rate limits)
      - Real-time status updates via WebSocket or polling (15s interval)
    - **Pipeline Monitor** (DESIGN.md:927):
      - Visual pipeline status: Fetch → Clean → Understand → Score → Store, each stage with count/error/latency
      - Currently processing items list with stage indicator
      - Failed items table with error details + "Retry" button
      - Use Recharts for latency/throughput charts
    - **Subgraph Match Audit** (DESIGN.md:928):
      - For any push, show WHY it was recommended: content_subgraph ↔ user_KG match visualization
      - Side-by-side comparison: content subgraph (left) + matched user KG nodes (right)
      - Score breakdown: prerequisite_coverage, concept_distance, difficulty_fit
    - **Strategy Tuning** (DESIGN.md:929):
      - Slider controls for: match_threshold, category_quotas (per content type), exploration ε
      - Changes take effect immediately (stored in user preferences, live-reloaded by ranker)
    - **Cost & Model Routing** (DESIGN.md:930):
      - Token usage chart (daily/weekly/monthly) by model (DeepSeek API vs Qwen local)
      - Average latency per LLM call type (gatekeeper, summarize, evaluate, explain)
      - Error/timeout rate
    - **Analytics Dashboard** (DESIGN.md:906-910):
      - Reading statistics: items read by day/week, time spent, domain distribution (pie chart)
      - Knowledge growth curve: total concepts mastered over time (line chart)
      - Source quality ranking: sources ranked by user positive feedback rate (bar chart)
      - Push accuracy trend: positive_rate over time (line chart)
    - Backend endpoints needed:
      - `GET /api/admin/pipeline/status` — real-time pipeline status
      - `GET /api/admin/pipeline/failed` — failed items with retry capability
      - `POST /api/admin/pipeline/retry/{item_id}` — retry failed item
      - `GET /api/admin/costs` — LLM token usage and costs
      - `GET /api/analytics/reading-stats?period=week|month` — reading statistics
      - `GET /api/analytics/knowledge-growth` — knowledge growth over time
      - `GET /api/analytics/source-quality` — source ranking
      - `GET /api/analytics/push-accuracy` — push accuracy trend

  **Must NOT do**:
  - Do NOT implement multi-user admin with RBAC — single user system, admin = the user
  - Do NOT implement real-time log streaming — use polling for pipeline status
  - Do NOT implement Prometheus/Grafana integration — built-in charts only
  - Do NOT implement A/B testing framework for strategy tuning

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Heavy frontend work with charts, tables, real-time status displays requiring polished UI/UX
  - **Skills**: [`frontend-ui-ux`, `playwright`]
    - `frontend-ui-ux`: Complex dashboard layouts with multiple chart types and interactive controls
    - `playwright`: QA testing for admin interactions
  - **Skills Evaluated but Omitted**:
    - `dev-browser`: Playwright skill sufficient

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 53, 54)
  - **Parallel Group**: Wave 4.2
  - **Blocks**: Task 58 (final E2E)
  - **Blocked By**: Task 30 (dashboard shell), Task 49 (connector list API), Task 13 (pipeline for monitoring), Task 20 (ranker for match audit)

  **References**:

  **Pattern References**:
  - `frontend/src/app/dashboard/` — Existing dashboard from Task 38, add admin routes
  - Folo reference: `Folo/apps/desktop/layer/renderer/src/modules/` — Panel/card layout patterns
  - `frontend/src/components/` — Existing shadcn/ui components

  **API/Type References**:
  - DESIGN.md:925-935 — Admin panel information architecture
  - DESIGN.md:906-910 — Data insights page specification
  - `src/api/` — Existing API structure, add admin/ and analytics/ routers

  **External References**:
  - Recharts docs: https://recharts.org/en-US/guide
  - shadcn/ui table: https://ui.shadcn.com/docs/components/table
  - TanStack Table: https://tanstack.com/table/latest

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `tests/unit/test_admin_api.py` — Pipeline status, cost, retry endpoints (8+ tests)
  - [ ] `tests/unit/test_analytics_api.py` — Reading stats, growth, accuracy endpoints (6+ tests)
  - [ ] `frontend/src/__tests__/pages/Admin.test.tsx` — Connector table, pipeline view rendering (5+ tests)
  - [ ] `frontend/src/__tests__/pages/Analytics.test.tsx` — Charts rendering with mock data (4+ tests)
  - [ ] `uv run pytest tests/unit/test_admin*.py tests/unit/test_analytics*.py -v && npx vitest run` → PASS (23+ tests)

  **QA Scenarios:**

  ```
  Scenario: Admin panel shows connector status table
    Tool: Playwright
    Preconditions: Dashboard running, 12 connectors registered, some with recent errors
    Steps:
      1. Navigate to http://localhost:3000/dashboard/admin/connectors
      2. Wait for table (selector: table[data-testid="connector-table"])
      3. Assert 12 rows in table body
      4. Assert columns: Name, Status, Last Fetch, Items, Errors, Actions
      5. Find a connector with status "error", assert error badge is red
      6. Click "Trigger Fetch" for RSS connector, wait 5s
      7. Assert status updates (via polling) to show recent last_fetch
    Expected Result: Full connector table with real-time status and manual trigger
    Failure Indicators: Empty table, missing connectors, trigger doesn't work
    Evidence: .sisyphus/evidence/task-55-connector-table.png

  Scenario: Analytics reading stats chart renders
    Tool: Playwright
    Preconditions: Dashboard running, user has 30+ days of reading history
    Steps:
      1. Navigate to http://localhost:3000/dashboard/analytics
      2. Wait for charts (selector: .recharts-wrapper)
      3. Assert at least 4 chart containers present
      4. Click "Monthly" period toggle on reading stats chart
      5. Assert chart redraws with monthly data
      6. Hover over a bar, assert tooltip shows count + domain breakdown
    Expected Result: 4+ charts rendered, interactive with period toggles and tooltips
    Failure Indicators: Empty charts, no data, tooltips missing
    Evidence: .sisyphus/evidence/task-55-analytics-charts.png

  Scenario: Pipeline monitor shows processing status
    Tool: Playwright
    Preconditions: Dashboard running, pipeline actively processing items
    Steps:
      1. Navigate to http://localhost:3000/dashboard/admin/pipeline
      2. Assert pipeline stages visible: Fetch, Clean, Understand, Score, Store
      3. Assert each stage shows item count and latency
      4. Find "Failed Items" section, assert table with error details visible
      5. Click "Retry" on a failed item, assert toast notification "Retry queued"
    Expected Result: Real-time pipeline visualization with retry capability
    Failure Indicators: No stages visible, counts all zero, retry fails
    Evidence: .sisyphus/evidence/task-55-pipeline-monitor.png
  ```

  **Commit**: YES
  - Message: `feat(admin): add admin panel with connector management, pipeline monitor, analytics dashboard`
  - Files: `frontend/src/app/dashboard/admin/`, `frontend/src/app/dashboard/analytics/`, `src/api/admin.py`, `src/api/analytics.py`, `tests/`
  - Pre-commit: `uv run pytest tests/unit/test_admin*.py tests/unit/test_analytics*.py -v && npx vitest run`

#### Wave 4.3 — Polish + Final Integration (Tasks 56-58)

- [ ] 56. Performance Optimization + Caching Layer

  **What to do**:
  - Implement caching strategy (DESIGN.md:1059-1067):
    - **Redis cache layer** for hot data:
      - User preferences: cache with 5min TTL, invalidate on update
      - KG neighborhood (top 50 nodes by mastery): cache with 10min TTL
      - Content quality scores: cache permanently (immutable after scoring), invalidate on re-score
      - Push batch results: cache with 30min TTL per user
      - Connector health status: cache with 1min TTL
    - Cache decorator: `@cached(ttl=300, key_prefix="user_prefs")` for service methods
    - Cache invalidation: event-driven via `cache_invalidate(pattern="user:{user_id}:*")` on writes
  - **Database query optimization**:
    - Add PostgreSQL indexes: content(source, created_at), push_record(user_id, created_at), feedback(user_id, content_id)
    - Neo4j query optimization: use parameterized queries, add indexes on concept.name and edge.type
    - Add `EXPLAIN ANALYZE` logging for queries exceeding 100ms
    - Implement connection pooling: asyncpg pool (min=5, max=20), neo4j driver session pool
  - **LLM cost optimization** (DESIGN.md:1059-1067):
    - Similar content dedup: before sending to LLM, check if content with >0.9 Jaccard similarity already exists → reuse summary
    - Batch LLM calls: accumulate up to 5 gatekeeper evaluations, send as single prompt with numbered items
    - Response caching: cache LLM responses by prompt hash in Redis (24hr TTL)
    - Token tracking: log tokens_used per LLM call to `llm_usage` table, expose via admin API
  - **Celery worker optimization**:
    - Configure prefetch_multiplier=1 (one task at a time for long-running LLM tasks)
    - Add task priority queues: `critical` (feedback), `default` (pipeline), `background` (reports)
    - Configure `task_soft_time_limit=300` and `task_time_limit=600` for LLM tasks
  - **Frontend performance**:
    - React Flow: virtualize nodes for graphs with >200 nodes (use React Flow's built-in viewport culling)
    - TanStack Query: configure staleTime=30s for analytics data, 5s for pipeline status
    - Bundle analysis: ensure main bundle < 500KB gzipped

  **Must NOT do**:
  - Do NOT add Prometheus/Grafana — built-in monitoring only
  - Do NOT implement distributed caching (single Redis instance sufficient for single user)
  - Do NOT implement CDN or edge caching
  - Do NOT optimize before profiling — each optimization must reference a measured bottleneck

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Cross-cutting performance concerns requiring careful profiling, cache invalidation logic, and database tuning
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `playwright`: No interactive UI testing needed, performance is measured via backend metrics

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 57)
  - **Parallel Group**: Wave 4.3
  - **Blocks**: Task 58 (final E2E should test optimized system)
  - **Blocked By**: ALL Phase 1-3 and Wave 4.1-4.2 tasks (optimize what exists)

  **References**:

  **Pattern References**:
  - `src/core/config.py` — Redis configuration, add cache settings
  - `src/services/` — All services that need caching applied
  - `src/models/` — All models that need index optimization

  **API/Type References**:
  - DESIGN.md:1059-1067 — Cost optimization strategy table
  - `src/core/database.py` — Database connection setup, add pooling config

  **External References**:
  - Redis caching patterns: https://redis.io/docs/manual/patterns/
  - asyncpg connection pooling: https://magicstack.github.io/asyncpg/current/api/index.html#connection-pools
  - Celery optimization: https://docs.celeryq.dev/en/stable/userguide/optimizing.html

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `tests/unit/test_cache.py` — Cache decorator, invalidation, TTL expiry (8+ tests)
  - [ ] `tests/unit/test_llm_dedup.py` — Content similarity dedup, batch calls (5+ tests)
  - [ ] `tests/unit/test_token_tracking.py` — Token usage logging and reporting (4+ tests)
  - [ ] `uv run pytest tests/unit/test_cache*.py tests/unit/test_llm_dedup*.py tests/unit/test_token*.py -v` → PASS (17+ tests)

  **QA Scenarios:**

  ```
  Scenario: Redis cache reduces repeated query latency
    Tool: Bash (curl + timing)
    Preconditions: API running with Redis cache enabled, user with KG data
    Steps:
      1. First call (cold): time curl -s http://localhost:8000/api/kg/graph?user_id=test_user > /dev/null
      2. Record latency_cold
      3. Second call (warm): time curl -s http://localhost:8000/api/kg/graph?user_id=test_user > /dev/null
      4. Record latency_warm
      5. Assert latency_warm < latency_cold * 0.5 (at least 50% faster)
      6. Verify Redis has cache key: redis-cli EXISTS "kg:graph:test_user"
    Expected Result: Cached response at least 2x faster, cache key exists in Redis
    Failure Indicators: No latency improvement, cache key missing
    Evidence: .sisyphus/evidence/task-56-cache-latency.txt

  Scenario: LLM response dedup avoids duplicate API calls
    Tool: Bash (curl)
    Preconditions: API running, two near-identical content items in DB
    Steps:
      1. Record current LLM call count: curl -s http://localhost:8000/api/admin/costs | jq '.total_calls'
      2. Trigger pipeline for content item A (new)
      3. Wait for processing, record new LLM call count
      4. Trigger pipeline for content item B (90%+ similar to A)
      5. Wait for processing, record final LLM call count
      6. Assert call count increase for B is 0 or 1 (dedup skipped most LLM calls)
    Expected Result: Second similar item reuses cached LLM results
    Failure Indicators: Same number of LLM calls for both items
    Evidence: .sisyphus/evidence/task-56-llm-dedup.json

  Scenario: Database indexes improve query performance
    Tool: Bash (psql)
    Preconditions: PostgreSQL running with 10000+ content rows
    Steps:
      1. Run EXPLAIN ANALYZE on content query by source + date range
      2. Assert query plan uses Index Scan (not Seq Scan)
      3. Assert execution time < 50ms
    Expected Result: Index scan used, query under 50ms
    Failure Indicators: Sequential scan, execution time > 200ms
    Evidence: .sisyphus/evidence/task-56-index-performance.txt
  ```

  **Commit**: YES
  - Message: `perf: add Redis caching, DB indexes, LLM dedup, Celery priority queues`
  - Files: `src/core/cache.py`, `src/core/database.py`, `src/services/`, `alembic/versions/`, `tests/`
  - Pre-commit: `uv run pytest tests/unit/test_cache*.py tests/unit/test_llm*.py tests/unit/test_token*.py -v`

- [ ] 57. Spaced Repetition Reminders via Telegram (FSRS)

  **What to do**:
  - Implement the cognitive retention system (DESIGN.md:1013-1037):
    - **Review scheduling** using FSRS algorithm (already implemented in Task 40):
      - Extend Task 40's FSRS implementation to generate Telegram review pushes
      - When a review is due (retrievability < threshold), create a review push record
      - Review pushes are distinct from regular content pushes — tagged with `push_type="review"`
    - **Review push format** (DESIGN.md:1027-1031):
      - Not raw content re-push. Three review modes, randomly selected:
       1. **Concept test**: "🧠 Pop quiz: What's the core optimization in FlashAttention?" (question first, answer hidden behind button)
       2. **New connection**: "You learned X before. Here's a new paper that builds on it from a different angle" (link new content to reviewed concept)
       3. **Application hint**: "Your current project uses Y. Remember the Z technique you learned? Could it apply here?" (only during project focus mode)
      - Use Jinja2 templates: `prompts/review_concept_test.j2`, `prompts/review_connection.j2`, `prompts/review_application.j2`
    - **Review interaction flow in Telegram**:
      - Concept test: Show question → user taps "Show answer" → show answer + ask "How well did you remember?" (🟢 Easy / 🟡 Good / 🟠 Hard / 🔴 Forgot)
      - Map response to FSRS rating: Easy=4, Good=3, Hard=2, Forgot=1
      - Update FSRS card parameters (stability, difficulty) based on rating
      - If "Forgot": auto-schedule follow-up review in 1 day + queue related prerequisite content
    - **Review scheduling Celery task**:
      - `check_due_reviews` runs every hour via Celery Beat
      - Checks all user's FSRS cards where `next_review <= now()`
      - Respects push_schedule time windows (no reviews during late_night)
      - Maximum 3 review pushes per day (configurable)
    - **Telegram commands**:
      - `/review` — manually trigger a review session (3-5 concept tests in sequence)
      - `/review_stats` — show retention statistics (avg retrievability, reviews done, streak)
    - **Internalization tracking** (DESIGN.md:1037):
      - If a concept is rated "Easy" 3 consecutive times, mark as "internalized" → exit review queue
      - If concept is frequently used in project focus mode, auto-mark as "internalized"

  **Must NOT do**:
  - Do NOT implement SRS as a standalone flashcard app — it's integrated into the push system
  - Do NOT implement custom spaced repetition algorithm — use FSRS from Task 40
  - Do NOT send review pushes outside configured time windows
  - Do NOT review low-value content — only content user explicitly marked as high-value (👍)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Complex state machine integrating FSRS algorithm with Telegram bot interaction and Celery scheduling
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `playwright`: No web UI, Telegram-only interaction

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 56)
  - **Parallel Group**: Wave 4.3
  - **Blocks**: Task 58 (final E2E includes review flow)
  - **Blocked By**: Task 40 (FSRS implementation), Task 14 (Telegram bot feedback handlers), Task 24 (push schedule/time windows)

  **References**:

  **Pattern References**:
  - `src/services/fsrs.py` — FSRS algorithm from Task 40, use for scheduling and rating updates
  - `src/services/push_scheduler.py` — Push scheduler from Task 24, add review push type
  - `src/bot/handlers/feedback.py` — Feedback handlers, extend with review rating buttons
  - `prompts/` — Existing Jinja2 templates

  **API/Type References**:
  - `src/models/fsrs.py:FSRSCard` — FSRS card model from Task 40
  - `src/models/push.py:PushRecord` — Add push_type field ("content" | "review")
  - DESIGN.md:1013-1037 — Cognitive retention system specification
  - DESIGN.md:1027-1031 — Review push format (3 modes)

  **External References**:
  - FSRS algorithm: https://github.com/open-spaced-repetition/fsrs4anki/wiki/The-Algorithm
  - DESIGN.md:1019 — R(t) = e^(-t/S) retention formula

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `tests/unit/test_review_scheduler.py` — Due review detection, time window respect, daily limit (8+ tests)
  - [ ] `tests/unit/test_review_push.py` — Three review modes generation, template rendering (6+ tests)
  - [ ] `tests/unit/test_review_interaction.py` — Rating mapping, FSRS update, internalization (6+ tests)
  - [ ] `tests/unit/test_review_commands.py` — /review and /review_stats Telegram commands (4+ tests)
  - [ ] `uv run pytest tests/unit/test_review*.py -v` → PASS (24+ tests)

  **QA Scenarios:**

  ```
  Scenario: Concept test review flow via Telegram
    Tool: interactive_bash (tmux)
    Preconditions: Bot running, test user has FSRS card for "FlashAttention" due for review
    Steps:
      1. Trigger review: send /review command to bot
      2. Wait 5s, assert bot sends concept test question about FlashAttention
      3. Assert "Show answer" button present
      4. Tap "Show answer"
      5. Assert answer revealed + rating buttons: 🟢 Easy / 🟡 Good / 🟠 Hard / 🔴 Forgot
      6. Tap "🟡 Good" (rating=3)
      7. Verify FSRS card updated: curl -s http://localhost:8000/api/kg/concept/flashattention/fsrs
      8. Assert next_review date is further in future than before
    Expected Result: Full review cycle with question, answer reveal, rating, FSRS update
    Failure Indicators: No question generated, buttons missing, FSRS not updated
    Evidence: .sisyphus/evidence/task-57-review-flow.txt

  Scenario: Automatic review scheduling respects time windows
    Tool: Bash (curl)
    Preconditions: API running, 5 FSRS cards due for review, current time in configured push window
    Steps:
      1. Manually trigger check_due_reviews task
      2. curl -s http://localhost:8000/api/push/pending?user_id=test_user&type=review
      3. Assert at most 3 review pushes created (daily limit)
      4. Assert all pushes have scheduled_time within allowed time window
    Expected Result: Max 3 reviews queued, all within time windows
    Failure Indicators: >3 reviews, reviews scheduled during late_night window
    Evidence: .sisyphus/evidence/task-57-review-schedule.json

  Scenario: Internalization auto-exit after 3 consecutive Easy ratings
    Tool: Bash (curl)
    Preconditions: API running, FSRS card for "Attention Mechanism" with 2 consecutive Easy ratings
    Steps:
      1. Simulate third Easy rating: curl -s -X POST http://localhost:8000/api/review/rate -d '{"concept": "attention-mechanism", "rating": 4}'
      2. Fetch FSRS card status: curl -s http://localhost:8000/api/kg/concept/attention-mechanism/fsrs
      3. Assert card status is "internalized" and is no longer in review queue
    Expected Result: Card marked as internalized, removed from review rotation
    Failure Indicators: Card still in review queue, status not updated
    Evidence: .sisyphus/evidence/task-57-internalization.json
  ```

  **Commit**: YES
  - Message: `feat(review): implement spaced repetition reminders with FSRS and 3 review modes`
  - Files: `src/services/review.py`, `src/tasks/review.py`, `src/bot/handlers/review.py`, `prompts/review_*.j2`, `tests/unit/test_review*.py`
  - Pre-commit: `uv run pytest tests/unit/test_review*.py -v`

- [ ] 58. Phase 4 Integration Tests + Full End-to-End Verification

  **What to do**:
  - Write comprehensive integration tests covering all Phase 4 features:
    - **Connector integration**: Trigger all 12 connectors in sequence, verify content flows through pipeline to storage
    - **Exploration integration**: Verify ε-greedy produces exploration items that pass quality floor, feed through ranker correctly
    - **QA dialog integration**: Full explain-concept flow from push card → concept selection → explanation → mastery update
    - **Export integration**: Generate content, accumulate positive feedback on topic, trigger topic aggregation, export as PDF
    - **Admin integration**: Verify admin panel data matches actual system state (connector health, pipeline status, costs)
    - **Review integration**: Mark content as high-value → FSRS card created → review scheduled → review push sent → rating recorded
  - Write full E2E test simulating a complete user journey:
    ```
    1. Cold start: User sends /start to Telegram bot
    2. Onboarding: Complete guided dialog (basic interests, background)
    3. Add sources: /subscribe with 3 RSS feeds
    4. First fetch cycle: Connectors fetch content, pipeline processes
    5. First push: User receives Telegram push, gives 👍 feedback
    6. Knowledge update: Verify KG updated with new concepts
    7. Explain concept: Tap ❓ on a push, select concept, receive explanation
    8. Second push cycle: Verify push ranking reflects feedback
    9. Exploration: Verify ε-greedy kicks in with cross-domain content
    10. Review: After 1 day (simulated), review push arrives for high-value content
    11. Report: After accumulating 5+ items, weekly report generated
    12. Export: Export topic report as PDF, verify contents
    13. Admin: Check admin panel reflects all activities accurately
    ```
  - Frontend E2E with Playwright:
    - Full dashboard navigation: Feed → KG visualization → Analytics → Admin → Settings
    - Content detail: click card, view AI analysis + subgraph + original content
    - KG interaction: zoom, filter, edit mastery, verify persistence
    - Export download: trigger and verify PDF download
  - Performance benchmark test:
    - Pipeline throughput: process 100 content items, measure total time, assert < 30 min
    - Push generation latency: generate push batch, assert < 5s
    - KG query latency: fetch 100-node subgraph, assert < 2s
    - Dashboard load time: full page load with data, assert < 3s

  **Must NOT do**:
  - Do NOT mock external APIs in E2E tests — use real (or recorded) responses
  - Do NOT skip any phase in the user journey test
  - Do NOT mark E2E tests as skipped — all must pass

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Complex cross-system integration testing requiring understanding of all system components and their interactions
  - **Skills**: [`playwright`]
    - `playwright`: Required for frontend E2E tests
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: Not building UI, just testing it

  **Parallelization**:
  - **Can Run In Parallel**: NO (must run after all other tasks)
  - **Parallel Group**: Wave 4.3 (sequential, after Tasks 56-57)
  - **Blocks**: Final Verification Wave
  - **Blocked By**: ALL Tasks 49-57

  **References**:

  **Pattern References**:
  - `tests/integration/test_phase1_integration.py` — Phase 1 integration test pattern from Task 26
  - `tests/integration/test_phase2_integration.py` — Phase 2 integration test pattern from Task 39
  - `tests/integration/test_phase3_integration.py` — Phase 3 integration test pattern from Task 48
  - `frontend/e2e/` — Existing Playwright E2E tests from Phase 3

  **API/Type References**:
  - All API endpoints across all phases
  - All models and schemas

  **External References**:
  - Playwright test docs: https://playwright.dev/docs/test-intro

  **Acceptance Criteria**:

  **TDD:**
  - [ ] `tests/integration/test_phase4_integration.py` — All Phase 4 feature integrations (12+ tests)
  - [ ] `tests/e2e/test_full_journey.py` — Complete user journey simulation (1 long test with 13 steps)
  - [ ] `tests/e2e/test_performance.py` — Performance benchmarks (4 tests)
  - [ ] `frontend/e2e/full-dashboard.spec.ts` — Full dashboard E2E (6+ tests)
  - [ ] `uv run pytest tests/integration/test_phase4*.py tests/e2e/ -v` → PASS (17+ tests)
  - [ ] `cd frontend && npx playwright test` → PASS (all E2E tests)

  **QA Scenarios:**

  ```
  Scenario: Complete user journey E2E (cold start to report)
    Tool: Bash (curl) + interactive_bash (tmux for Telegram)
    Preconditions: Full system running via docker-compose (all 6 services), fresh database
    Steps:
      1. Send /start to Telegram bot, complete onboarding questions
      2. Send /subscribe https://feeds.arstechnica.com/arstechnica/index
      3. Wait 60s for connector fetch + pipeline processing
      4. Send /feed to trigger manual push
      5. Verify push received with content card
      6. Tap 👍 on the push
      7. Verify KG updated: curl -s http://localhost:8000/api/kg/stats | jq '.total_concepts'
      8. Assert total_concepts > 0
      9. Tap ❓ on same push, select a concept, receive explanation
      10. Send /review to trigger review session
      11. Complete review with 🟡 Good rating
      12. Repeat steps 4-6 for 5 pushes to accumulate feedback
      13. Check weekly report: curl -s http://localhost:8000/api/reports/latest
      14. Assert report exists with reading_count >= 5
    Expected Result: Full end-to-end journey completes without errors
    Failure Indicators: Any step returns error, KG not updated, report not generated
    Evidence: .sisyphus/evidence/task-58-full-journey.txt

  Scenario: Dashboard E2E navigation
    Tool: Playwright
    Preconditions: Dashboard running at localhost:3000, user has data from journey test
    Steps:
      1. Navigate to http://localhost:3000/dashboard
      2. Assert feed cards visible (selector: [data-testid="content-card"])
      3. Click Knowledge Graph nav item
      4. Assert graph renders (selector: .react-flow__renderer) with nodes
      5. Click Analytics nav item
      6. Assert charts render (selector: .recharts-wrapper)
      7. Click Admin nav item
      8. Assert connector table visible with 12+ rows
      9. Click on a content card, verify detail page shows AI analysis + subgraph + original
    Expected Result: All dashboard pages load with real data, navigation works
    Failure Indicators: Empty pages, navigation errors, missing data
    Evidence: .sisyphus/evidence/task-58-dashboard-e2e.png

  Scenario: Performance benchmarks pass
    Tool: Bash (curl + timing)
    Preconditions: System running with 1000+ content items, 100+ KG concepts
    Steps:
      1. Measure pipeline throughput: trigger 100 items, time total processing
      2. Assert total time < 1800s (30 min)
      3. Measure push generation: time curl -s http://localhost:8000/api/push/generate?user_id=test_user
      4. Assert latency < 5s
      5. Measure KG query: time curl -s 'http://localhost:8000/api/kg/graph?user_id=test_user&depth=3'
      6. Assert latency < 2s
      7. Measure dashboard load: use Playwright to time full page load
      8. Assert load time < 3s
    Expected Result: All 4 benchmarks pass
    Failure Indicators: Any benchmark exceeds threshold
    Evidence: .sisyphus/evidence/task-58-performance-benchmarks.json
  ```

  **Commit**: YES
  - Message: `test(phase4): comprehensive integration tests, E2E journey, and performance benchmarks`
  - Files: `tests/integration/test_phase4_integration.py`, `tests/e2e/`, `frontend/e2e/full-dashboard.spec.ts`
  - Pre-commit: `uv run pytest tests/integration/test_phase4*.py -v && cd frontend && npx playwright test`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Rejection → fix → re-run.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, curl endpoint, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `uv run ruff check .` + `uv run mypy .` + `uv run pytest tests/ -v`. Review all changed files for: `type: ignore`, bare `except:`, `print()` in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names (data/result/item/temp). Run `cd frontend && npm run lint && npm run build` for Next.js (Phase 2+).
  Output: `Ruff [PASS/FAIL] | Mypy [PASS/FAIL] | Pytest [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Agent-Executed QA Sweep** — `unspecified-high` (+ `playwright` skill for web UI)
  Start from clean state (`docker compose down -v && docker compose up -d`). Execute EVERY QA scenario from EVERY completed phase. Test: RSS fetches real content, pipeline processes end-to-end, Telegram bot responds, feedback updates DB. For Phase 2+: Playwright tests on web UI. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance per phase. Detect cross-task contamination. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

> Group commits by logical unit. Each task gets its own commit unless explicitly grouped.
> Python-related pre-commit commands should run via `uv run ...`.

| Wave | Commit Message | Files | Pre-commit |
|------|---------------|-------|------------|
| 0.1 | `chore(infra): scaffold project + Docker Compose + dev tooling` | docker-compose.yml, pyproject.toml, Makefile, .env.example, alembic/ | `uv run ruff check .` |
| 0.1 | `feat(db): PostgreSQL schema + Alembic migrations` | alembic/versions/, src/models/ | `uv run pytest tests/unit/test_models.py` |
| 0.1 | `feat(core): Pydantic models + LLM abstraction + prompts` | src/schemas/, src/llm/, prompts/ | `uv run pytest tests/unit/` |
| 0.2 | `feat(connectors): RSS/Atom + arXiv with full-text extraction` | src/connectors/ | `uv run pytest tests/unit/test_connectors.py` |
| 0.2 | `feat(pipeline): gatekeeper + understanding + scoring services` | src/services/ | `uv run pytest tests/unit/test_services.py` |
| 0.3 | `feat(pipeline): orchestrator + state machine` | src/pipeline/ | `uv run pytest tests/unit/test_pipeline.py` |
| 0.3 | `feat(bot): Telegram bot + feedback handler` | src/bot/ | `uv run pytest tests/unit/test_bot.py` |
| 0.4 | `test(e2e): integration tests + smoke test` | tests/integration/ | `uv run pytest tests/ -v` |
| 0.4 | `docs: update DESIGN.md - fix 9 inconsistencies` | DESIGN.md | — |
| 1.x | `feat(scoring): 7-dimension quality scoring + push ranking` | src/services/scoring.py, src/services/ranking.py | `uv run pytest tests/` |
| 1.x | `feat(search): Meilisearch integration + dedup` | src/services/search.py, docker-compose.yml | `uv run pytest tests/` |
| 2.x | `feat(graph): Neo4j setup + knowledge graph + subgraph gen` | src/graph/, docker-compose.yml | `uv run pytest tests/` |
| 2.x | `feat(frontend): Next.js dashboard - feed, detail, settings` | frontend/ | `cd frontend && npm run lint && npm run build` |
| 3.x | `feat(cognitive): FSRS + memory system + reports` | src/services/, frontend/src/app/reports/ | `uv run pytest tests/` |
| 4.x | `feat(connectors): 10+ additional content sources` | src/connectors/ | `uv run pytest tests/` |
| 4.x | `feat(explore): ε-greedy + QA flow + KG visualization` | src/, frontend/ | `uv run pytest tests/ && cd frontend && npm run build` |

---

## Success Criteria

### Verification Commands
```bash
# Phase 0 smoke test
docker compose up -d && sleep 15
docker compose ps  # Expected: all 6 services healthy
curl -sf http://localhost:8000/health  # Expected: {"status":"ok"}
curl -sf http://localhost:8000/api/v1/connectors/rss/fetch -d '{"feed_url":"https://hnrss.org/frontpage","limit":3}' | uv run python -m json.tool  # Expected: items array with 3 entries
uv run pytest tests/ -v --tb=short  # Expected: all pass, 0 failures

# Phase 1
curl -sf http://localhost:8000/api/v1/content?scored=true | uv run python -m json.tool  # Expected: items with quality_score fields
curl -sf http://localhost:7700/indexes  # Expected: Meilisearch content index exists

# Phase 2
curl -sf http://localhost:7474  # Expected: Neo4j browser accessible
curl -sf http://localhost:3000  # Expected: Next.js dashboard loads
uv run pytest tests/ -v  # Expected: all pass including graph tests

# Phase 3
curl -sf http://localhost:8000/api/v1/reports/weekly  # Expected: generated report
uv run pytest tests/ -v  # Expected: all pass including FSRS tests

# Phase 4
uv run pytest tests/ -v  # Expected: all pass, full coverage
docker compose logs --tail=100  # Expected: no errors in last 100 lines
```

### Final Checklist
- [ ] All "Must Have" present and verified
- [ ] All "Must NOT Have" absent (no vector DB, no Neo4j GDS, no Celery chains)
- [ ] All tests pass (`uv run pytest tests/ -v` and `cd frontend && npx vitest run` for frontend)
- [ ] Docker Compose starts cleanly on both local laptop and VPS
- [ ] DESIGN.md updated with all 9 corrections
- [ ] Each phase has passing E2E smoke test
- [ ] Evidence directory populated for all QA scenarios
