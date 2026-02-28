<div align="center">

```
     _    _ _
    / \  | (_) ___ ___
   / _ \ | | |/ __/ _ \
  / ___ \| | | (_|  __/
 /_/   \_\_|_|\___\___|
```

**Your AI-Powered Information Secretary**

Cuts through information noise to surface what matters —<br/>
personalized ranking · knowledge-graph-aware push · a feedback loop that learns

<br/>

[![Python](https://img.shields.io/badge/Python-≥3.12-3776AB?logo=python&logoColor=fff)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=fff)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js_16-000?logo=nextdotjs&logoColor=fff)](https://nextjs.org/)
[![Neo4j](https://img.shields.io/badge/Neo4j-4581C3?logo=neo4j&logoColor=fff)](https://neo4j.com/)
[![Celery](https://img.shields.io/badge/Celery-37814A?logo=celery&logoColor=fff)](https://docs.celeryq.dev/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=fff)](https://www.docker.com/)

![Version](https://img.shields.io/badge/version-0.1.0_Early_Beta-E5A00D?style=flat)
![License](https://img.shields.io/badge/license-MIT-green?style=flat)

[Getting Started](#-getting-started) · [Architecture](#-architecture) · [Features](#-core-features) · [API](#-api-reference) · [Testing](#-testing) · [Commands](#%EF%B8%8F-cheat-sheet)

**[🇨🇳 中文文档](README_ZH.md)**

</div>

---

## 📖 Table of Contents

- [📖 Table of Contents](#-table-of-contents)
- [🌟 Overview](#-overview)
- [🏗 Architecture](#-architecture)
- [🛠 Tech Stack](#-tech-stack)
  - [Backend](#backend)
  - [AI](#ai)
  - [Frontend](#frontend)
  - [Infrastructure](#infrastructure)
- [🌐 Service Topology](#-service-topology)
- [✨ Core Features](#-core-features)
  - [📡 Data Sources](#-data-sources)
  - [🔄 Pipeline (6 Stages)](#-pipeline-6-stages)
  - [📊 Push Ranking (P\_score)](#-push-ranking-p_score)
  - [🧠 7-Dimension Quality Scoring](#-7-dimension-quality-scoring)
  - [🕸️ Knowledge Graph](#️-knowledge-graph)
  - [👤 User System](#-user-system)
- [📂 Project Structure](#-project-structure)
- [🚀 Getting Started](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [1️⃣ Configure Environment Variables](#1️⃣-configure-environment-variables)
  - [2️⃣ Start Backend Services](#2️⃣-start-backend-services)
  - [3️⃣ Start Frontend](#3️⃣-start-frontend)
  - [4️⃣ Verify](#4️⃣-verify)
- [📡 API Reference](#-api-reference)
- [⏰ Scheduled Tasks](#-scheduled-tasks)
- [🖥 Frontend Pages](#-frontend-pages)
- [🧪 Testing](#-testing)
  - [Backend](#backend-1)
  - [Frontend](#frontend-1)
  - [Test Coverage Overview](#test-coverage-overview)
- [⌨️ Cheat Sheet](#️-cheat-sheet)
- [❓ FAQ](#-faq)
- [⚠️ Known Limitations](#️-known-limitations)
- [📚 Documentation](#-documentation)
- [📊 Status](#-status)

---

## 🌟 Overview

Alice implements a complete **Fetch → Understand → Score → Index → Push → Feedback** closed loop:

```
RSS / arXiv
     │
     ▼
┌─────────┐    ┌──────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  Fetch   │───▶│  Gatekeeper  │───▶│  Understanding   │───▶│ Graph Extraction │
│          │    │  (Ollama)    │    │   (DeepSeek)     │    │     (Neo4j)      │
└─────────┘    └──────────────┘    └──────────────────┘    └────────┬─────────┘
                                                                    │
                    ┌───────────────────────────────────────────────┘
                    ▼
             ┌──────────┐    ┌───────────────┐    ┌──────────┐    ┌──────────┐
             │ Scoring  │───▶│   Indexing     │───▶│   Push   │───▶│ Feedback │
             │(DeepSeek)│    │ (Meilisearch) │    │(Telegram)│    │(KG update)│
             └──────────┘    └───────────────┘    └──────────┘    └──────────┘
```

Each stage runs as an independent Celery task (no chaining). State is persisted to PostgreSQL, enabling fault recovery and automatic retries.

---

## 🏗 Architecture

```
                          ┌──────────────────────────────────────────────┐
                          │          Frontend (Next.js 16 + React 19)    │
                          │   Feed │ Search │ Dashboard │ KG │ Settings  │
                          └─────────────────┬────────────────────────────┘
                                            │ X-API-Key (cookie)
                          ┌─────────────────▼────────────────────────────┐
                          │          API Layer (FastAPI :8000)            │
                          │     APIKeyMiddleware → 9 Router Modules      │
                          └──┬──────────┬──────────┬──────────┬──────────┘
                             │          │          │          │
                ┌────────────▼──┐  ┌────▼─────┐ ┌─▼───────┐  │
                │  19 Services  │  │  Celery  │ │   Bot   │  │
                │ (business     │  │  Worker  │ │ (:8081) │  │
                │  logic)       │  │          │ │         │  │
                └──┬──┬──┬──────┘  └────┬─────┘ └────┬────┘  │
                   │  │  │              │            │       │
          ┌────────▼┐ │  ▼              │            │       │
          │PostgreSQL│ │ Neo4j 5        │            │       │
          │   16     │ │ (knowledge     │            │       │
          │          │ │  graph)        │            │       │
          └──────────┘ │                │            │       │
                       ▼                │            │       │
                 Meilisearch ◄──────────┘            │       │
                   v1.6                              │       │
                                                     │       │
                  Redis 7 ◄──────────────────────────┘       │
                 (Broker)                                     │
```

---

## 🛠 Tech Stack

<table>
<tr>
<td>

### Backend

| Component | Choice |
|:----------|:-------|
| 🌐 Web Framework | FastAPI + Uvicorn |
| 📋 Task Queue | Celery + Redis |
| 🗃️ ORM | SQLAlchemy 2.0 async + Alembic |
| 🤖 Telegram | aiogram 3 (webhook) |
| 📦 Package Manager | [uv](https://docs.astral.sh/uv/) |
| 📝 Logging | structlog (JSON) |

</td>
<td>

### AI

| Component | Choice |
|:----------|:-------|
| 🧠 Primary LLM | DeepSeek API |
| 🏠 Local Model | Ollama (qwen2.5:1.5b) |
| 🔌 Abstraction | `LLMClient` Protocol |
| 🧪 Test Mock | `MockLLMClient` |

</td>
</tr>
<tr>
<td>

### Frontend

| Component | Choice |
|:----------|:-------|
| ⚛️ Framework | Next.js 16 + React 19 |
| 🎨 Styling | Tailwind CSS 4 + shadcn/ui |
| 📊 State | Zustand 5 |
| 📈 Charts | Recharts 3 |
| 🕸️ Graph Viz | @xyflow/react 12 |

</td>
<td>

### Infrastructure

| Component | Choice |
|:----------|:-------|
| 🐘 Primary DB | PostgreSQL 16 |
| 🔍 Full-text Search | Meilisearch v1.6 |
| 🕸️ Knowledge Graph | Neo4j 5 + APOC |
| ⚡ Cache / Broker | Redis 7 |
| 🐳 Containerization | Docker Compose |

</td>
</tr>
</table>

---

## 🌐 Service Topology

| Service | Description | Port |
|:--------|:------------|:----:|
| 🌐 `api` | FastAPI application server | `8000` |
| 🤖 `bot` | Telegram Bot (webhook) | `8081` |
| ⚙️ `worker` | Celery task worker | — |
| ⏰ `scheduler` | Celery Beat scheduler | — |
| 🐘 `postgres` | PostgreSQL primary database | `5432` |
| ⚡ `redis` | Redis (broker + backend) | `6379` |
| 🔍 `meilisearch` | Full-text search engine | `7700` |
| 🕸️ `neo4j` | Knowledge graph database | `7474` / `7687` |

---

## ✨ Core Features

### 📡 Data Sources

| Connector | Description |
|:----------|:------------|
| **RSS / Atom** | General feed subscriptions with custom fetch intervals |
| **arXiv** | Academic paper search and ingestion |

### 🔄 Pipeline (6 Stages)

| Stage | Status Flag | Description |
|:------|:------------|:------------|
| **Fetch** | `fetched` | Pull raw content, URL normalization |
| **Gatekeeper** | `gatekept` | Fast local-model filtering via Ollama (rule-based fallback) |
| **Understanding** | `understood` | DeepSeek generates summary, key points, domain tags, reading time |
| **Graph Extraction** | — | Extract concept subgraph into Neo4j (best-effort, non-blocking) |
| **Scoring** | `scored` | 7-dimension quality scoring |
| **Indexing** | `indexed` | Write to Meilisearch index, compute initial P_score |

### 📊 Push Ranking (P_score)

```
P = Q × R × T × D × U + ε
```

| Factor | Meaning |
|:-------|:--------|
| **Q** | Normalized quality score |
| **R** | User-content relevance (KG coverage + concept distance + difficulty fit) |
| **T** | Time window score (quiet hours / work / weekend) |
| **D** | Time decay (breaking news 24h half-life, knowledge 7d) |
| **U** | Urgency |
| **ε** | Exploration factor (reserved, currently fixed at 0.0) |

### 🧠 7-Dimension Quality Scoring

`substance` · `novelty` · `density` · `credibility` · `actionability` · `social` · `timeliness`

### 🕸️ Knowledge Graph

- Concept nodes + relationship extraction (`PREREQUISITE_OF` / `EXTENDS` / `APPLIES_TO` / `CONTRASTS`)
- User `KNOWS` edges with mastery score maintenance
- Leiden community detection → knowledge cluster visualization
- Knowledge gap analysis (low-mastery neighbors of high-mastery nodes)
- Feedback-driven KG updates (positive +0.15, negative −0.1, already known → 1.0)

### 👤 User System

| Feature | Description |
|:--------|:------------|
| **4 Modes** | daily / project / explore / low_energy (auto 23:00–07:00) |
| **3-Layer Memory** | working (current focus) / short-term (14d decay) / long-term |
| **FSRS v5** | Spaced repetition review cards + streak tracking |
| **Reactive Skills** | YAML-defined feedback handlers (KG update / preference tuning / difficulty calibration) |

---

## 📂 Project Structure

```
alice/
├── 📄 pyproject.toml              # Python project config (uv + hatch)
├── 🐳 docker-compose.yml          # 8-service orchestration
├── 🐳 Dockerfile                  # Multi-stage build (Python 3.12-slim)
├── 📄 Makefile                    # Dev command shortcuts
├── 📄 alembic.ini                 # DB migration config
│
├── src/alice/                     # 🐍 Python backend
│   ├── api/v1/                    #   9 router modules
│   ├── bot/                       #   Telegram Bot (webhook + handlers)
│   ├── config/                    #   Pydantic Settings + scoring weights
│   ├── connectors/                #   RSS + arXiv source adapters
│   ├── graph/                     #   Neo4j client / repo / subgraph extractor / user KG
│   ├── llm/                       #   LLMClient protocol + DeepSeek / Ollama / Mock
│   ├── models/                    #   SQLAlchemy models (6 core tables)
│   ├── pipeline/                  #   Celery tasks + scheduler
│   ├── schemas/                   #   Pydantic request / response schemas
│   ├── services/                  #   19 business logic services
│   ├── worker/                    #   Celery app factory + legacy compat
│   ├── db.py                      #   Async SQLAlchemy engine + session
│   ├── main.py                    #   FastAPI entry point
│   └── prompts.py                 #   Jinja2 prompt template loader
│
├── prompts/                       # 📝 LLM prompt templates (*.j2)
├── config/                        # ⚙️ skills.yaml
├── alembic/versions/              # 🗃️ 6 database migration versions
│
├── tests/                         # 🧪 Tests
│   ├── unit/                      #   37 unit test modules
│   ├── integration/               #   8 integration test modules
│   └── fixtures/                  #   Test data (RSS / arXiv / LLM responses)
│
└── frontend/                      # ⚛️ Next.js frontend
    ├── src/app/                   #   7 page routes
    ├── src/components/            #   UI components
    ├── src/lib/                   #   API client / store / types
    └── e2e/                       #   Playwright E2E tests
```

---

## 🚀 Getting Started

### Prerequisites

| Tool | Note |
|:-----|:-----|
| 🐳 Docker & Docker Compose | Required |
| 📦 Node.js ≥ 18 | Frontend development |
| 🐍 [uv](https://docs.astral.sh/uv/) | Python package manager (only needed for local backend dev) |

### 1️⃣ Configure Environment Variables

```bash
cp .env.example .env
```

**Required variables:**

| Variable | Description |
|:---------|:------------|
| `DEEPSEEK_API_KEY` | DeepSeek API key (for Understanding + Scoring) |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot token (for push notifications) |
| `TELEGRAM_WEBHOOK_HOST` | Bot webhook callback URL |

> 💡 All other variables have sensible defaults for development. **Make sure to replace all default secrets in production.**

### 2️⃣ Start Backend Services

<details>
<summary><b>Option A: Full Docker Stack (Recommended)</b></summary>

```bash
# Start all services (including Bot)
docker compose up -d

# Or without Bot
docker compose up -d postgres redis meilisearch neo4j api worker scheduler

# Run database migrations
docker compose exec api alembic upgrade head
```

</details>

<details>
<summary><b>Option B: Docker Infrastructure + Local Python</b></summary>

```bash
# Start infrastructure
docker compose up -d postgres redis meilisearch neo4j

# Install Python dependencies + run migrations
uv sync --extra dev
uv run alembic upgrade head

# Start in separate terminals (4 processes)
uv run uvicorn alice.main:app --host 0.0.0.0 --port 8000 --reload
uv run celery -A alice.worker.celery_app worker --loglevel=info \
  -Q celery,pipeline,fetch,push --pool=threads --concurrency=4
uv run celery -A alice.worker.celery_app beat --loglevel=info
uv run python -m alice.bot.main   # optional
```

</details>

### 3️⃣ Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000/login` and enter your `ALICE_API_KEY` (default: `alicesecret`).

### 4️⃣ Verify

```bash
# Health check
curl http://localhost:8000/health

# Add a data source
curl -X POST http://localhost:8000/api/v1/sources \
  -H "X-API-Key: alicesecret" \
  -H "Content-Type: application/json" \
  -d '{"name": "HN", "url": "https://hnrss.org/frontpage", "type": "rss"}'

# Trigger fetch
curl -X POST http://localhost:8000/api/v1/pipeline/fetch/trigger \
  -H "X-API-Key: alicesecret"
```

---

## 📡 API Reference

All `/api/*` routes require an `X-API-Key` header. `/health`, `/docs`, `/openapi.json`, and `/redoc` are public.

| Module | Endpoint Prefix | Description |
|:-------|:----------------|:------------|
| 📄 Content | `/api/v1/content` | List / detail / delete / batch delete |
| 📡 Sources | `/api/v1/sources` | Data source CRUD |
| 🔄 Pipeline | `/api/v1/pipeline` | Status / fetch trigger / push trigger / retry |
| 🔍 Search | `/api/v1/search` | Full-text search / hybrid search / autocomplete |
| 💬 Feedback | `/api/v1/feedback` | User feedback submission |
| ⚙️ Settings | `/api/v1/settings` | Push preferences read/write |
| 📊 Dashboard | `/api/v1/dashboard` | Cognitive dashboard statistics |
| 🕸️ KG | `/api/v1/kg` | Knowledge graph queries / communities / gap analysis |
| 🔌 Connectors | `/api/v1/connectors` | RSS fetch debugging |

> 📖 Full interactive docs available at **http://localhost:8000/docs** after startup.

---

## ⏰ Scheduled Tasks

| Task | Interval | Queue |
|:-----|:---------|:------|
| Full fetch | Every 30 min | `fetch` |
| Push dispatch | Every 20 min | `push` |
| Failed retry | Every 6 hours | `pipeline` |
| P_score batch update | Every 24 hours | `pipeline` |

> Each source also has its own dynamic schedule based on `fetch_interval_minutes` + random jitter.

---

## 🖥 Frontend Pages

| Route | Description |
|:------|:------------|
| `/feed` | Infinite-scroll feed, grid/list views, batch actions, feedback |
| `/search` | Full-text + hybrid search, autocomplete, filters |
| `/content/[id]` | Magazine-style detail, AI summary + key-point cards, subgraph visualization |
| `/dashboard` | Cognitive dashboard: learning velocity / knowledge growth / memory overview / FSRS review / community clusters |
| `/dashboard/knowledge-graph` | Interactive knowledge graph visualization (React Flow) |
| `/settings` | Source management / push preferences / schedule / user mode |
| `/login` | API Key authentication |

---

## 🧪 Testing

### Backend

```bash
# Unit tests
uv run pytest tests/unit -v

# Integration tests (requires Docker infrastructure)
docker compose up -d
uv run pytest tests/integration -m integration -v

# Graph integration tests (requires Neo4j + Ollama)
TEST_DATABASE_URL="postgresql+asyncpg://alice:alice@localhost:5432/alice_test" \
NEO4J_TEST_URI="bolt://localhost:7687" \
NEO4J_TEST_USER="neo4j" \
NEO4J_TEST_PASS="alice_neo4j" \
uv run pytest tests/integration/test_phase2_integration.py -m integration -v
```

### Frontend

```bash
cd frontend

# Component / logic tests (Vitest)
npm run test

# E2E tests (Playwright)
npm run test:e2e
```

### Test Coverage Overview

| Layer | Scale | Notes |
|:------|:------|:------|
| Backend Unit | 37 modules, 300+ cases | Covers all services, connectors, graph, LLM, pipeline, bot |
| Backend Integration | 8 modules | Real DB / graph deps enabled via env vars |
| Frontend Unit | Vitest | Component and logic tests |
| Frontend E2E | Playwright | Page-level end-to-end verification |

---

## ⌨️ Cheat Sheet

```bash
make up              # 🐳 docker compose up -d
make down            # 🐳 docker compose down
make test            # 🧪 Run all pytest tests
make test-phase2     # 🧪 Graph integration tests
make lint            # 🔍 ruff check
make format          # ✨ ruff format
make migrate         # 🗃️ alembic upgrade head
make logs            # 📋 docker compose logs -f
make shell           # 🐍 Python REPL
make clean           # 🧹 Remove cache files
```

---

## ❓ FAQ

<details>
<summary><b><code>401 Invalid API key</code></b></summary>

The request is missing the `X-API-Key` header, or the key doesn't match the `ALICE_API_KEY` environment variable. Default value is `alicesecret`.

</details>

<details>
<summary><b>Schema mismatch / missing tables</b></summary>

Run database migrations:

```bash
make migrate
# or
docker compose exec api alembic upgrade head
```

</details>

<details>
<summary><b>Search returns 503</b></summary>

Check Meilisearch service health:

```bash
curl http://localhost:7700/health
```

</details>

<details>
<summary><b>Pipeline stuck at <code>fetched</code></b></summary>

Verify the worker process is running and listening on the `pipeline` queue:

```bash
docker compose logs -f worker
```

</details>

<details>
<summary><b>Bot not responding</b></summary>

Check that `TELEGRAM_BOT_TOKEN` and `TELEGRAM_WEBHOOK_HOST` are configured correctly. The bot requires a publicly accessible webhook URL.

</details>

---

## ⚠️ Known Limitations

> Current version is **0.1.0 Early Beta**. Known technical debt and limitations:

| Category | Details |
|:---------|:--------|
| 🔒 Security | Default API key must be replaced in production; bot has no user authentication |
| 🧪 Testing | Some integration tests still use patch isolation; frontend E2E coverage is thin |
| 🤖 Gatekeeper | Falls back to rule-based filtering when Ollama is unavailable |
| 🔗 Legacy | `alice.worker.tasks` retains legacy task name compatibility |
| 📊 Ranking | Exploration factor ε is currently fixed at 0.0 |
| 👥 Multi-user | Frontend currently hardcodes userId=1; multi-user support is WIP |
| 🕸️ GraphRAG | Semantic search channel not yet implemented |

> Full audit report available in `AUDIT_REPORT.md`

---

## 📚 Documentation

| Document | Description |
|:---------|:------------|
| 📖 [README.md](README.md) | This document — project overview and quickstart |
| 🇨🇳 [README_ZH.md](README_ZH.md) | Chinese version of this document |
| 🏗️ [DESIGN.md](DESIGN.md) | Technical design — architecture details and module design |
| 🤝 [AGENTS.md](AGENTS.md) | Development conventions — engineering principles and code standards |
| 🔍 [AUDIT_REPORT.md](AUDIT_REPORT.md) | Code audit report — tech debt and improvement suggestions |
| 💡 [idea.md](idea.md) | Product vision — requirements draft and future roadmap |

---

## 📊 Status

![Repobeats analytics](https://repobeats.axiom.co/api/embed/804172554acbfa044e815782ff8c848bde477070.svg "Repobeats analytics image")

---

<p align="center">
  <sub>Built with ❤️ using FastAPI · Next.js · Neo4j · DeepSeek</sub>
</p>