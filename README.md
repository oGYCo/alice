# Alice — AI Secretary

> 当前仓库的**唯一可信运行手册**（以代码为准，持续同步更新）。

## 0. 当前实现快照（2026-02-27）

Alice 是一个个人智能信息管理系统，当前仓库已经包含可运行的：

- FastAPI 后端 API（`/api/v1/*`）
- aiogram Bot 独立服务（webhook + feedback callback）
- Celery Worker + Beat（分阶段任务，不使用 chain）
- PostgreSQL / Redis / Meilisearch / Neo4j
- Next.js 前端（Feed / Search / Settings / Login）

已落地的数据源：

- `rss`
- `arxiv`

已落地核心链路：

- source 创建 -> 拉取 -> 入库 -> gatekeeper -> understanding -> graph extraction -> scoring -> indexing -> push

## 1. 技术栈与服务端口

| Service | Stack | Port |
| --- | --- | --- |
| `api` | FastAPI + Uvicorn | `8000` |
| `bot` | aiogram + aiohttp webhook | `8081` |
| `worker` | Celery worker | - |
| `scheduler` | Celery beat | - |
| `postgres` | PostgreSQL 16 | `5432` |
| `redis` | Redis 7 (AOF enabled) | `6379` |
| `meilisearch` | Meilisearch v1.6 | `7700` |
| `neo4j` | Neo4j 5 | `7474` / `7687` |

## 2. 目录结构（与当前代码一致）

```text
alice/
├── README.md
├── DESIGN.md
├── AGENTS.md
├── docker-compose.yml
├── pyproject.toml
├── alembic/
├── prompts/                # Jinja2 prompt templates (*.j2)
├── src/alice/
│   ├── api/v1/             # content/sources/pipeline/search/settings/feedback/connectors
│   ├── bot/                # Telegram bot webhook service
│   ├── config/
│   ├── connectors/         # rss + arxiv
│   ├── graph/
│   ├── llm/                # deepseek / ollama / mock
│   ├── models/
│   ├── pipeline/           # active celery tasks
│   ├── schemas/
│   ├── services/
│   ├── worker/             # legacy task-name compatibility + celery app
│   ├── db.py
│   ├── main.py
│   └── prompts.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
└── frontend/
    ├── src/
    ├── e2e/
    └── package.json
```

## 3. 环境变量（真实可运行配置）

先复制：

```bash
cp .env.example .env
```

推荐本机开发 `.env`（Python 服务运行在宿主机）示例：

```dotenv
# Core
DATABASE_URL=postgresql+asyncpg://alice:alice@localhost:5432/alice?ssl=disable
CELERY_BROKER_URL=redis://localhost:6379/0
REDIS_URL=redis://localhost:6379/0
LOG_LEVEL=INFO
DEBUG=false

# Auth
ALICE_API_KEY=alicesecret

# LLM
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
OLLAMA_HOST=http://host.docker.internal:11434

# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_HOST=

# Search / Graph
MEILISEARCH_URL=http://localhost:7700
MEILISEARCH_API_KEY=masterKey
NEO4J_URI=bolt://localhost:7687
NEO4J_AUTH=neo4j/alice_neo4j

# Frontend rewrite target
API_URL=http://localhost:8000
NEXT_PUBLIC_API_URL=
```

说明：

- `docker-compose.yml` 已对容器内服务地址做覆盖（`postgres`/`redis`/`meilisearch`/`neo4j`），不会受你本机 `.env` 中 `localhost` 写法影响。
- `ALICE_API_KEY` 是后端 `/api/*` 的强制鉴权密钥，前后端都要一致。
- 生产环境请务必替换所有默认密钥和密码。

## 4. 启动方式 A（推荐）: Docker 跑后端全家桶 + 本机跑前端

### 4.1 启动后端与基础设施

不需要 Bot：

```bash
docker compose up -d postgres redis meilisearch neo4j api worker scheduler
```

需要 Bot：

```bash
docker compose up -d
```

### 4.2 执行迁移

```bash
docker compose exec api alembic upgrade head
```

### 4.3 基础健康检查

```bash
curl http://localhost:8000/health
curl http://localhost:8081/health
```

## 5. API 鉴权（必须）

后端中间件要求：`/api/*` 必须带 `X-API-Key`。

```bash
export ALICE_API_KEY=alicesecret
```

示例：

```bash
curl -X POST http://localhost:8000/api/v1/sources \
  -H "X-API-Key: ${ALICE_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"name":"HN RSS","url":"https://hnrss.org/frontpage","type":"rss"}'

curl "http://localhost:8000/api/v1/content?limit=20&offset=0&sort=relevance" \
  -H "X-API-Key: ${ALICE_API_KEY}"

curl -X POST http://localhost:8000/api/v1/pipeline/fetch/trigger \
  -H "X-API-Key: ${ALICE_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{}'

curl "http://localhost:8000/api/v1/pipeline/status" \
  -H "X-API-Key: ${ALICE_API_KEY}"
```

## 6. 启动方式 B: 本机多进程运行 Python 服务

### 6.1 先启动基础设施

```bash
docker compose up -d postgres redis meilisearch neo4j
```

### 6.2 安装依赖 + 迁移

```bash
uv sync --extra dev
uv run alembic upgrade head
```

### 6.3 分终端启动

```bash
# API
uv run uvicorn alice.main:app --host 0.0.0.0 --port 8000 --reload

# Worker
uv run celery -A alice.worker.celery_app worker --loglevel=info -Q celery,pipeline,fetch,push --pool=threads --concurrency=4

# Beat
uv run celery -A alice.worker.celery_app beat --loglevel=info

# Bot (可选)
uv run python -m alice.bot.main
```

## 7. 前端启动与登录

```bash
cd frontend
npm install
npm run dev
```

- 打开 `http://localhost:3000/login`
- 输入与后端一致的 `ALICE_API_KEY`
- 登录后进入 Feed / Search / Settings

## 8. 测试策略（真实环境优先）

### 8.1 单元测试

```bash
uv run pytest tests/unit -v
cd frontend && npm run test
```

### 8.2 后端集成测试（真实 PostgreSQL / 可选 Neo4j）

集成测试直接连接 `docker-compose.yml` 的真实服务，使用独立的 `alice_test` 数据库（自动创建）：

```bash
docker compose up -d
uv run pytest tests/integration -m integration -v
```

Phase 2 图谱相关测试需再设置：

```bash
export NEO4J_TEST_URI="bolt://localhost:7687"
export NEO4J_TEST_USER="neo4j"
export NEO4J_TEST_PASS="alice_neo4j"
```

直接运行 `test_phase2_integration.py`（避免因缺少环境变量被 skip）：

```bash
TEST_DATABASE_URL="postgresql+asyncpg://alice:alice@localhost:5432/alice_test" \
NEO4J_TEST_URI="bolt://localhost:7687" \
NEO4J_TEST_USER="neo4j" \
NEO4J_TEST_PASS="alice_neo4j" \
PHASE2_LLM_PROVIDER="ollama" \
uv run pytest tests/integration/test_phase2_integration.py -m integration -v
```

### 8.3 前端 E2E

```bash
cd frontend
npm run test:e2e
```

说明：

- 当前 integration 套件中，部分用例仍会对外部网络/Celery dispatch 做隔离（patch），这是历史兼容做法。
- 按本仓库开发原则，新增或重构关键链路时必须补充“真实依赖接入”的验收测试，不允许只做 mock 路径验证。

## 9. 强制开发原则（本仓库执行标准）

1. 测试驱动必须引入真实数据和真实环境运行，不能只停留在纯单元测试。
2. 新模块开发必须与原系统集成验证，禁止“只写模块不接入主流程”。
3. 生产路径禁止模拟逻辑，必须使用真实运行逻辑。
4. 相关配置必须是生产可运行的真实配置，禁止杜撰参数。
5. 禁止以 `TODO` 注释替代实现，需求必须完整落地。

## 10. 常见问题

- `401 Invalid API key`
  - 请求缺少 `X-API-Key` 或密钥不一致。
- `Database schema mismatch`
  - 运行 `uv run alembic upgrade head`（或 `docker compose exec api alembic upgrade head`）。
- Search 503
  - 检查 `meilisearch` 服务状态和 `MEILISEARCH_URL`。

## 11. 常用命令速查

```bash
# Backend
uv sync --extra dev
uv run ruff check .
uv run pytest
uv run alembic upgrade head

# Docker
docker compose up -d
docker compose logs -f api
docker compose logs -f worker
docker compose down

# Frontend
cd frontend
npm run lint
npm run typecheck
npm run test
npm run test:e2e
```
