# Alice — AI Secretary

个人智能信息管理系统：从信息噪音中筛选高价值内容，基于用户知识状态做个性化排序与推送。

> 本文档以代码为准，持续同步更新。详细设计见 `DESIGN.md`，开发约定见 `AGENTS.md`。

---

## 系统概览

Alice 实现了完整的 **采集 → 理解 → 评分 → 索引 → 推送 → 反馈** 闭环：

```
RSS/arXiv ──fetch──▶ Gatekeeper ──▶ Understanding ──▶ Graph Extraction
                       (Ollama)       (DeepSeek)        (Neo4j)
                                                           │
                             ┌─────────────────────────────┘
                             ▼
                        Scoring ──▶ Indexing ──▶ Push ──▶ Feedback
                       (DeepSeek)  (Meilisearch) (Telegram)  (KG update)
```

每阶段独立 Celery 任务，不使用 chain；状态持久化到 PostgreSQL，支持故障恢复与自动重试。

## 技术栈

| 层级 | 选型 |
|------|------|
| 后端 API | FastAPI + Uvicorn |
| 任务队列 | Celery + Redis（broker/backend） |
| ORM | SQLAlchemy 2.0 async + Alembic |
| Telegram Bot | aiogram 3（webhook 模式） |
| 前端 | Next.js 16 App Router + Tailwind + shadcn/ui |
| 状态管理 | Zustand + TanStack Query |
| 主存储 | PostgreSQL 16 |
| 全文检索 | Meilisearch v1.6 |
| 知识图谱 | Neo4j 5 + APOC |
| LLM | DeepSeek API（主），Ollama qwen2.5:1.5b（gatekeeper） |
| 包管理 | uv（Python），npm（前端） |
| 日志 | structlog（JSON 结构化） |

## 服务端口

| 服务 | 端口 |
|------|------|
| API (FastAPI) | 8000 |
| Bot (aiogram) | 8081 |
| PostgreSQL | 5432 |
| Redis | 6379 |
| Meilisearch | 7700 |
| Neo4j Browser / Bolt | 7474 / 7687 |

## 核心功能

### 数据源

- **RSS/Atom** — 通用 Feed 订阅，支持自定义抓取间隔
- **arXiv** — 学术论文搜索与抓取

### Pipeline（6 阶段）

| 阶段 | 状态 | 说明 |
|------|------|------|
| Fetch | `fetched` | 拉取原始内容，URL 归一化 + SimHash 去重 |
| Gatekeeper | `gatekept` | Ollama 本地模型快速筛选，规则回退兜底 |
| Understanding | `understood` | DeepSeek 生成摘要、关键点、领域标签、阅读时长 |
| Graph Extraction | — | 从理解结果提取概念子图写入 Neo4j（best-effort，不阻塞） |
| Scoring | `scored` | 7 维质量评分（substance / novelty / density / credibility / actionability / social / timeliness） |
| Indexing | `indexed` | 写入 Meilisearch 索引，计算初始 P_score |

### 推送排序（P_score）

```
P = Q × R × T × D × U + ε
```

- **Q** — 质量分归一化
- **R** — 用户-内容匹配度（基于知识图谱前置覆盖 + 概念距离 + 难度拟合）
- **T** — 时间窗口评分（安静时段 / 工作 / 周末）
- **D** — 时间衰减（时效性内容 24h 半衰期，知识性 7 天）
- **U** — 紧急度
- **ε** — 探索因子（预留）

### 知识图谱

- 概念节点 + 关系抽取（PREREQUISITE_OF / EXTENDS / APPLIES_TO / CONTRASTS）
- 用户 KNOWS 关系 + mastery 分数维护
- Leiden 社区检测 → 知识聚类可视化
- 知识缺口分析（高 mastery 节点邻居中的低 mastery 候选）
- 反馈驱动的 KG 更新（正面 +0.15，负面 −0.1，已知 → 1.0）

### 用户系统

- **4 种模式**：daily / project / explore / low_energy（23:00–07:00 自动低能量）
- **三层记忆**：working（当前焦点）/ short-term（14 天衰减）/ long-term
- **FSRS v5** 间隔重复：复习卡片 + 打卡统计
- **反应式技能**：5 个 YAML 定义的反馈处理技能（KG 更新 / 偏好调整 / 难度校准等）

### 前端页面

| 页面 | 功能 |
|------|------|
| `/feed` | 无限滚动信息流，grid/list 视图，批量操作，反馈入口 |
| `/search` | 全文搜索 + 混合搜索（graph + text + semantic），自动补全，过滤器 |
| `/content/[id]` | Magazine 风格详情，AI 摘要 + 关键点卡片，关联子图可视化 |
| `/dashboard` | 认知仪表盘：学习速度 / 知识增长 / 记忆概览 / FSRS 复习 / 社区聚类 / 模式指示 |
| `/dashboard/knowledge-graph` | 交互式知识图谱可视化（React Flow） |
| `/settings` | 数据源管理 / 推送偏好 / 时间表 / 用户模式 |
| `/login` | API Key 认证 |

## 目录结构

```
├── src/alice/
│   ├── api/v1/           # 路由层（content / sources / pipeline / search / settings / feedback / dashboard / kg / connectors）
│   ├── bot/              # Telegram bot（webhook + handlers）
│   ├── config/           # Pydantic Settings + 评分权重配置
│   ├── connectors/       # RSS + arXiv 数据源适配器
│   ├── graph/            # Neo4j client / repository / subgraph extractor / user KG
│   ├── llm/              # LLMClient 协议 + DeepSeek / Ollama / Mock 实现
│   ├── models/           # SQLAlchemy 模型（content / source / user / feedback / review_card / user_memory）
│   ├── pipeline/         # Celery 任务 + 调度器 + 编排器
│   ├── schemas/          # Pydantic 请求/响应 schema
│   ├── services/         # 业务逻辑层（20 个服务模块）
│   ├── worker/           # Celery app 工厂 + legacy 兼容
│   ├── db.py             # 异步 SQLAlchemy engine + session
│   ├── main.py           # FastAPI 入口
│   └── prompts.py        # Jinja2 prompt 加载
├── prompts/              # LLM prompt 模板（*.j2）
├── config/               # skills.yaml
├── alembic/              # 数据库迁移（5 个版本）
├── tests/
│   ├── unit/             # 38 个单元测试模块
│   ├── integration/      # 8 个集成测试模块
│   └── fixtures/         # 测试数据（RSS / arXiv / LLM 响应）
├── frontend/
│   ├── src/app/          # Next.js pages
│   ├── src/components/   # UI 组件（feed / content / dashboard / graph / settings / layout）
│   ├── src/lib/          # API client / store / types
│   └── e2e/              # Playwright E2E 测试
├── docker-compose.yml
├── Dockerfile            # 多阶段构建（Python 3.12-slim）
├── Makefile
└── pyproject.toml
```

## 快速开始

### 前置条件

- Docker & Docker Compose
- Node.js ≥ 18
- [uv](https://docs.astral.sh/uv/)（Python 包管理，可选：仅本机运行后端时需要）

### 1. 配置环境变量

```bash
cp .env.example .env
```

必须填写的变量：

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥（Understanding + Scoring 必需） |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token（推送功能必需） |
| `TELEGRAM_WEBHOOK_HOST` | Bot webhook 回调地址 |

其余变量有合理默认值，开发环境可直接使用。生产环境**务必替换**所有默认密钥。

### 2. 启动服务

**方式 A：Docker 全栈（推荐）**

```bash
# 启动全部（含 Bot）
docker compose up -d

# 或不含 Bot
docker compose up -d postgres redis meilisearch neo4j api worker scheduler

# 执行数据库迁移
docker compose exec api alembic upgrade head
```

**方式 B：基础设施 Docker + 本机运行 Python**

```bash
# 基础设施
docker compose up -d postgres redis meilisearch neo4j

# Python 依赖 + 迁移
uv sync --extra dev
uv run alembic upgrade head

# 分终端启动（4 个进程）
uv run uvicorn alice.main:app --host 0.0.0.0 --port 8000 --reload
uv run celery -A alice.worker.celery_app worker --loglevel=info -Q celery,pipeline,fetch,push --pool=threads --concurrency=4
uv run celery -A alice.worker.celery_app beat --loglevel=info
uv run python -m alice.bot.main   # 可选
```

### 3. 启动前端

```bash
cd frontend && npm install && npm run dev
```

访问 `http://localhost:3000/login`，输入 `ALICE_API_KEY`（默认 `alicesecret`）登录。

### 4. 验证

```bash
# 健康检查
curl http://localhost:8000/health

# 添加数据源
curl -X POST http://localhost:8000/api/v1/sources \
  -H "X-API-Key: alicesecret" \
  -H "Content-Type: application/json" \
  -d '{"name":"HN","url":"https://hnrss.org/frontpage","type":"rss"}'

# 触发抓取
curl -X POST http://localhost:8000/api/v1/pipeline/fetch/trigger \
  -H "X-API-Key: alicesecret"
```

## API

所有 `/api/*` 路由需携带 `X-API-Key` 头。`/health`、`/docs`、`/openapi.json` 免鉴权。

| 模块 | 端点前缀 | 功能 |
|------|----------|------|
| Content | `/api/v1/content` | 内容列表 / 详情 / 删除 / 批量删除 |
| Sources | `/api/v1/sources` | 数据源 CRUD |
| Pipeline | `/api/v1/pipeline` | 状态查询 / 抓取触发 / 推送触发 / 重试 |
| Search | `/api/v1/search` | 全文搜索 / 混合搜索 / 自动补全 |
| Feedback | `/api/v1/feedback` | 用户反馈提交 |
| Settings | `/api/v1/settings` | 推送偏好读写 |
| Dashboard | `/api/v1/dashboard` | 认知仪表盘统计 |
| KG | `/api/v1/kg` | 知识图谱查询 / 社区 / 缺口分析 / 编辑 |
| Connectors | `/api/v1/connectors` | RSS 拉取调试 |

完整 API 文档：启动后访问 `http://localhost:8000/docs`。

## 定时任务

| 任务 | 周期 | 队列 |
|------|------|------|
| 全量抓取 | 每 30 分钟 | fetch |
| 推送调度 | 每 20 分钟 | push |
| 失败重试 | 每 6 小时 | pipeline |
| P_score 批量更新 | 每 24 小时 | pipeline |

各数据源还有独立的动态调度（基于 `fetch_interval_minutes` + 随机 jitter）。

## 测试

```bash
# 后端单元测试
uv run pytest tests/unit -v

# 后端集成测试（需先启动 Docker 基础设施）
docker compose up -d
uv run pytest tests/integration -m integration -v

# 图谱集成测试（需 Neo4j + Ollama）
TEST_DATABASE_URL="postgresql+asyncpg://alice:alice@localhost:5432/alice_test" \
NEO4J_TEST_URI="bolt://localhost:7687" \
NEO4J_TEST_USER="neo4j" \
NEO4J_TEST_PASS="alice_neo4j" \
uv run pytest tests/integration/test_phase2_integration.py -m integration -v

# 前端单元测试
cd frontend && npm run test

# 前端 E2E
cd frontend && npm run test:e2e
```

## 命令速查

```bash
make up              # docker compose up -d
make down            # docker compose down
make test            # pytest 全量
make test-phase2     # 图谱集成测试
make lint            # ruff check
make format          # ruff format
make migrate         # alembic upgrade head
make logs            # docker compose logs -f
make clean           # 清除缓存文件
```

## 常见问题

| 症状 | 解决 |
|------|------|
| `401 Invalid API key` | 请求缺少 `X-API-Key` 头或密钥与 `ALICE_API_KEY` 不一致 |
| Schema mismatch | 运行 `make migrate` 或 `docker compose exec api alembic upgrade head` |
| Search 503 | 检查 Meilisearch 服务状态：`curl http://localhost:7700/health` |
| Pipeline 卡在 `fetched` | 确认 worker 进程已启动且监听 `pipeline` 队列 |
| Bot 无响应 | 检查 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_WEBHOOK_HOST` 配置 |

## 已知技术债

- 部分集成测试仍使用 patch 隔离网络/Celery dispatch
- Gatekeeper 在 Ollama 不可用时存在规则回退路径
- `alice.worker.tasks` 保留 legacy 任务名兼容
- 探索因子 ε 当前固定为 0.0
