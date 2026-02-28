<div align="center">

<img src=".github/assets/banner.svg" width="100%" alt="Alice — AI 智能信息秘书" />

<br/>

[![Python](https://img.shields.io/badge/Python-≥3.12-3776AB?logo=python&logoColor=fff)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=fff)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js_16-000?logo=nextdotjs&logoColor=fff)](https://nextjs.org/)
[![Neo4j](https://img.shields.io/badge/Neo4j-4581C3?logo=neo4j&logoColor=fff)](https://neo4j.com/)
[![Celery](https://img.shields.io/badge/Celery-37814A?logo=celery&logoColor=fff)](https://docs.celeryq.dev/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=fff)](https://www.docker.com/)

![Version](https://img.shields.io/badge/version-0.1.0_Early_Beta-E5A00D?style=flat)
![License](https://img.shields.io/badge/license-MIT-green?style=flat)

[快速开始](#-快速开始) · [架构](#-系统架构) · [功能](#-核心功能) · [API](#-api-参考) · [测试](#-测试) · [命令](#️-命令速查)

**[🇬🇧 English](README.md)**

</div>

---

## 📖 目录

- [📖 目录](#-目录)
- [🌟 系统概览](#-系统概览)
- [🏗 系统架构](#-系统架构)
- [🛠 技术栈](#-技术栈)
  - [后端](#后端)
  - [AI](#ai)
  - [前端](#前端)
  - [基础设施](#基础设施)
- [🌐 服务拓扑](#-服务拓扑)
- [✨ 核心功能](#-核心功能)
  - [📡 数据源](#-数据源)
  - [🔄 Pipeline（6 阶段）](#-pipeline6-阶段)
  - [📊 推送排序（P\_score）](#-推送排序p_score)
  - [🧠 7 维质量评分](#-7-维质量评分)
  - [🕸️ 知识图谱](#️-知识图谱)
  - [👤 用户系统](#-用户系统)
- [📂 目录结构](#-目录结构)
- [🚀 快速开始](#-快速开始)
  - [前置条件](#前置条件)
  - [1️⃣ 配置环境变量](#1️⃣-配置环境变量)
  - [2️⃣ 启动后端服务](#2️⃣-启动后端服务)
  - [3️⃣ 启动前端](#3️⃣-启动前端)
  - [4️⃣ 验证](#4️⃣-验证)
- [📡 API 参考](#-api-参考)
- [⏰ 定时任务](#-定时任务)
- [🖥 前端页面](#-前端页面)
- [🧪 测试](#-测试)
  - [后端](#后端-1)
  - [前端](#前端-1)
  - [测试覆盖概况](#测试覆盖概况)
- [⌨️ 命令速查](#️-命令速查)
- [❓ 常见问题](#-常见问题)
- [⚠️ 已知局限](#️-已知局限)
- [📚 文档索引](#-文档索引)
- [📊 Status](#-status)

---

## 🌟 系统概览

Alice 实现了完整的 **采集 → 理解 → 评分 → 索引 → 推送 → 反馈** 闭环：

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
             │(DeepSeek)│    │ (Meilisearch) │    │(Telegram)│    │(KG 更新) │
             └──────────┘    └───────────────┘    └──────────┘    └──────────┘
```

每阶段为独立 Celery 任务（不使用 chain），状态持久化到 PostgreSQL，支持故障恢复与自动重试。

---

## 🏗 系统架构

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
                │  (业务逻辑)    │  │  Worker  │ │ (:8081) │  │
                └──┬──┬──┬──────┘  └────┬─────┘ └────┬────┘  │
                   │  │  │              │            │       │
          ┌────────▼┐ │  ▼              │            │       │
          │PostgreSQL│ │ Neo4j 5        │            │       │
          │   16     │ │ (知识图谱)      │            │       │
          └──────────┘ │                │            │       │
                       ▼                │            │       │
                 Meilisearch ◄──────────┘            │       │
                   v1.6                              │       │
                                                     │       │
                  Redis 7 ◄──────────────────────────┘       │
                 (Broker)                                     │
```

---

## 🛠 技术栈

<table>
<tr>
<td>

### 后端

| 组件 | 选型 |
|:-----|:-----|
| 🌐 Web 框架 | FastAPI + Uvicorn |
| 📋 任务队列 | Celery + Redis |
| 🗃️ ORM | SQLAlchemy 2.0 async + Alembic |
| 🤖 Telegram | aiogram 3 (webhook) |
| 📦 包管理 | [uv](https://docs.astral.sh/uv/) |
| 📝 日志 | structlog (JSON) |

</td>
<td>

### AI

| 组件 | 选型 |
|:-----|:-----|
| 🧠 主力 LLM | DeepSeek API |
| 🏠 本地模型 | Ollama (qwen2.5:1.5b) |
| 🔌 抽象层 | `LLMClient` Protocol |
| 🧪 测试 mock | `MockLLMClient` |

</td>
</tr>
<tr>
<td>

### 前端

| 组件 | 选型 |
|:-----|:-----|
| ⚛️ 框架 | Next.js 16 + React 19 |
| 🎨 样式 | Tailwind CSS 4 + shadcn/ui |
| 📊 状态 | Zustand 5 |
| 📈 图表 | Recharts 3 |
| 🕸️ 图可视化 | @xyflow/react 12 |

</td>
<td>

### 基础设施

| 组件 | 选型 |
|:-----|:-----|
| 🐘 主存储 | PostgreSQL 16 |
| 🔍 全文检索 | Meilisearch v1.6 |
| 🕸️ 知识图谱 | Neo4j 5 + APOC |
| ⚡ 缓存/Broker | Redis 7 |
| 🐳 容器化 | Docker Compose |

</td>
</tr>
</table>

---

## 🌐 服务拓扑

| 服务 | 说明 | 端口 |
|:-----|:-----|:----:|
| 🌐 `api` | FastAPI 应用服务 | `8000` |
| 🤖 `bot` | Telegram Bot (webhook) | `8081` |
| ⚙️ `worker` | Celery 任务执行进程 | — |
| ⏰ `scheduler` | Celery Beat 定时调度 | — |
| 🐘 `postgres` | PostgreSQL 主数据库 | `5432` |
| ⚡ `redis` | Redis (broker + backend) | `6379` |
| 🔍 `meilisearch` | 全文检索引擎 | `7700` |
| 🕸️ `neo4j` | 知识图谱数据库 | `7474` / `7687` |

---

## ✨ 核心功能

### 📡 数据源

| 连接器 | 说明 |
|:-------|:-----|
| **RSS / Atom** | 通用 Feed 订阅，支持自定义抓取间隔 |
| **arXiv** | 学术论文搜索与抓取 |

### 🔄 Pipeline（6 阶段）

| 阶段 | 状态标记 | 说明 |
|:-----|:---------|:-----|
| **Fetch** | `fetched` | 拉取原始内容，URL 归一化 |
| **Gatekeeper** | `gatekept` | Ollama 本地模型快速筛选（不可用时规则回退） |
| **Understanding** | `understood` | DeepSeek 生成摘要、关键点、领域标签、阅读时长 |
| **Graph Extraction** | — | 从理解结果提取概念子图写入 Neo4j（best-effort） |
| **Scoring** | `scored` | 7 维质量评分 |
| **Indexing** | `indexed` | 写入 Meilisearch 索引，计算初始 P_score |

### 📊 推送排序（P_score）

```
P = Q × R × T × D × U + ε
```

| 因子 | 含义 |
|:-----|:-----|
| **Q** | 质量分归一化 |
| **R** | 用户-内容匹配度（知识图谱覆盖 + 概念距离 + 难度拟合） |
| **T** | 时间窗口评分（安静时段 / 工作 / 周末） |
| **D** | 时间衰减（时效性 24h 半衰期，知识性 7 天） |
| **U** | 紧急度 |
| **ε** | 探索因子（预留，当前固定 0.0） |

### 🧠 7 维质量评分

`substance` · `novelty` · `density` · `credibility` · `actionability` · `social` · `timeliness`

### 🕸️ 知识图谱

- 概念节点 + 关系抽取（`PREREQUISITE_OF` / `EXTENDS` / `APPLIES_TO` / `CONTRASTS`）
- 用户 `KNOWS` 关系 + mastery 分数维护
- Leiden 社区检测 → 知识聚类可视化
- 知识缺口分析（高 mastery 邻居中的低 mastery 候选）
- 反馈驱动的 KG 更新（正向 +0.15，负向 −0.1，已知 → 1.0）

### 👤 用户系统

| 特性 | 说明 |
|:-----|:-----|
| **4 种模式** | daily / project / explore / low_energy（23:00–07:00 自动） |
| **三层记忆** | working（当前焦点）/ short-term（14 天衰减）/ long-term |
| **FSRS v5** | 间隔重复复习卡片 + 打卡统计 |
| **反应式技能** | YAML 定义的反馈处理技能（KG 更新 / 偏好调整 / 难度校准等） |

---

## 📂 目录结构

```
alice/
├── 📄 pyproject.toml              # Python 项目配置 (uv + hatch)
├── 🐳 docker-compose.yml          # 8 服务编排
├── 🐳 Dockerfile                  # 多阶段构建 (Python 3.12-slim)
├── 📄 Makefile                    # 开发命令快捷入口
├── 📄 alembic.ini                 # 数据库迁移配置
│
├── src/alice/                     # 🐍 Python 后端
│   ├── api/v1/                    #   9 个路由模块
│   ├── bot/                       #   Telegram Bot (webhook + handlers)
│   ├── config/                    #   Pydantic Settings + 评分权重
│   ├── connectors/                #   RSS + arXiv 数据源适配器
│   ├── graph/                     #   Neo4j 客户端 / 仓库 / 子图抽取 / 用户 KG
│   ├── llm/                       #   LLMClient 协议 + DeepSeek / Ollama / Mock
│   ├── models/                    #   SQLAlchemy 模型 (6 张核心表)
│   ├── pipeline/                  #   Celery 任务 + 调度器
│   ├── schemas/                   #   Pydantic 请求 / 响应 Schema
│   ├── services/                  #   19 个业务逻辑服务
│   ├── worker/                    #   Celery app 工厂 + legacy 兼容
│   ├── db.py                      #   异步 SQLAlchemy engine + session
│   ├── main.py                    #   FastAPI 应用入口
│   └── prompts.py                 #   Jinja2 prompt 模板加载
│
├── prompts/                       # 📝 LLM Prompt 模板 (*.j2)
├── config/                        # ⚙️ skills.yaml
├── alembic/versions/              # 🗃️ 6 个数据库迁移版本
│
├── tests/                         # 🧪 测试
│   ├── unit/                      #   37 个单元测试模块
│   ├── integration/               #   8 个集成测试模块
│   └── fixtures/                  #   测试数据 (RSS / arXiv / LLM 响应)
│
└── frontend/                      # ⚛️ Next.js 前端
    ├── src/app/                   #   7 个页面路由
    ├── src/components/            #   UI 组件
    ├── src/lib/                   #   API client / store / types
    └── e2e/                       #   Playwright E2E 测试
```

---

## 🚀 快速开始

### 前置条件

| 工具 | 说明 |
|:-----|:-----|
| 🐳 Docker & Docker Compose | 必需 |
| 📦 Node.js ≥ 18 | 前端开发 |
| 🐍 [uv](https://docs.astral.sh/uv/) | Python 包管理（仅本机运行后端时需要） |

### 1️⃣ 配置环境变量

```bash
cp .env.example .env
```

**必填变量：**

| 变量 | 说明 |
|:-----|:-----|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥（Understanding + Scoring） |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token（推送功能） |
| `TELEGRAM_WEBHOOK_HOST` | Bot webhook 回调地址 |

> 💡 其余变量有合理默认值，开发环境可直接使用。**生产环境务必替换所有默认密钥。**

### 2️⃣ 启动后端服务

<details>
<summary><b>方式 A：Docker 全栈（推荐）</b></summary>

```bash
# 启动全部服务（含 Bot）
docker compose up -d

# 或排除 Bot
docker compose up -d postgres redis meilisearch neo4j api worker scheduler

# 执行数据库迁移
docker compose exec api alembic upgrade head
```

</details>

<details>
<summary><b>方式 B：基础设施 Docker + 本机 Python</b></summary>

```bash
# 启动基础设施
docker compose up -d postgres redis meilisearch neo4j

# 安装 Python 依赖 + 迁移
uv sync --extra dev
uv run alembic upgrade head

# 分终端启动（4 个进程）
uv run uvicorn alice.main:app --host 0.0.0.0 --port 8000 --reload
uv run celery -A alice.worker.celery_app worker --loglevel=info \
  -Q celery,pipeline,fetch,push --pool=threads --concurrency=4
uv run celery -A alice.worker.celery_app beat --loglevel=info
uv run python -m alice.bot.main   # 可选
```

</details>

### 3️⃣ 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 `http://localhost:3000/login`，输入 `ALICE_API_KEY`（默认 `alicesecret`）登录。

### 4️⃣ 验证

```bash
# 健康检查
curl http://localhost:8000/health

# 添加数据源
curl -X POST http://localhost:8000/api/v1/sources \
  -H "X-API-Key: alicesecret" \
  -H "Content-Type: application/json" \
  -d '{"name": "HN", "url": "https://hnrss.org/frontpage", "type": "rss"}'

# 触发抓取
curl -X POST http://localhost:8000/api/v1/pipeline/fetch/trigger \
  -H "X-API-Key: alicesecret"
```

---

## 📡 API 参考

所有 `/api/*` 路由需携带 `X-API-Key` 请求头。`/health`、`/docs`、`/openapi.json`、`/redoc` 免鉴权。

| 模块 | 端点前缀 | 功能 |
|:-----|:---------|:-----|
| 📄 Content | `/api/v1/content` | 内容列表 / 详情 / 删除 / 批量删除 |
| 📡 Sources | `/api/v1/sources` | 数据源 CRUD |
| 🔄 Pipeline | `/api/v1/pipeline` | 状态查询 / 抓取触发 / 推送触发 / 重试 |
| 🔍 Search | `/api/v1/search` | 全文搜索 / 混合搜索 / 自动补全 |
| 💬 Feedback | `/api/v1/feedback` | 用户反馈提交 |
| ⚙️ Settings | `/api/v1/settings` | 推送偏好读写 |
| 📊 Dashboard | `/api/v1/dashboard` | 认知仪表盘统计 |
| 🕸️ KG | `/api/v1/kg` | 知识图谱查询 / 社区 / 缺口分析 |
| 🔌 Connectors | `/api/v1/connectors` | RSS 拉取调试 |

> 📖 完整交互式文档：启动后访问 **http://localhost:8000/docs**

---

## ⏰ 定时任务

| 任务 | 周期 | 队列 |
|:-----|:-----|:-----|
| 全量抓取 | 每 30 分钟 | `fetch` |
| 推送调度 | 每 20 分钟 | `push` |
| 失败重试 | 每 6 小时 | `pipeline` |
| P_score 批量更新 | 每 24 小时 | `pipeline` |

> 各数据源还有独立的动态调度（基于 `fetch_interval_minutes` + 随机 jitter）。

---

## 🖥 前端页面

| 路由 | 功能 |
|:-----|:-----|
| `/feed` | 无限滚动信息流，grid/list 视图，批量操作，反馈入口 |
| `/search` | 全文搜索 + 混合搜索，自动补全，过滤器 |
| `/content/[id]` | Magazine 风格详情，AI 摘要 + 关键点卡片，关联子图可视化 |
| `/dashboard` | 认知仪表盘：学习速度 / 知识增长 / 记忆概览 / FSRS 复习 / 社区聚类 |
| `/dashboard/knowledge-graph` | 交互式知识图谱可视化（React Flow） |
| `/settings` | 数据源管理 / 推送偏好 / 时间表 / 用户模式 |
| `/login` | API Key 认证 |

---

## 🧪 测试

### 后端

```bash
# 单元测试
uv run pytest tests/unit -v

# 集成测试（需先启动 Docker 基础设施）
docker compose up -d
uv run pytest tests/integration -m integration -v

# 图谱集成测试（需 Neo4j + Ollama）
TEST_DATABASE_URL="postgresql+asyncpg://alice:alice@localhost:5432/alice_test" \
NEO4J_TEST_URI="bolt://localhost:7687" \
NEO4J_TEST_USER="neo4j" \
NEO4J_TEST_PASS="alice_neo4j" \
uv run pytest tests/integration/test_phase2_integration.py -m integration -v
```

### 前端

```bash
cd frontend

# 组件 / 逻辑测试 (Vitest)
npm run test

# E2E 测试 (Playwright)
npm run test:e2e
```

### 测试覆盖概况

| 层级 | 规模 | 说明 |
|:-----|:-----|:-----|
| 后端单元测试 | 37 个模块，300+ 用例 | 覆盖全部 service、connectors、graph、LLM、pipeline、bot |
| 后端集成测试 | 8 个模块 | 真实 DB / 图谱依赖按环境变量启用 |
| 前端单元测试 | Vitest | 组件与逻辑测试 |
| 前端 E2E | Playwright | 页面级端到端验证 |

---

## ⌨️ 命令速查

```bash
make up              # 🐳 docker compose up -d
make down            # 🐳 docker compose down
make test            # 🧪 pytest 全量运行
make test-phase2     # 🧪 图谱集成测试
make lint            # 🔍 ruff check
make format          # ✨ ruff format
make migrate         # 🗃️ alembic upgrade head
make logs            # 📋 docker compose logs -f
make shell           # 🐍 Python REPL
make clean           # 🧹 清除缓存文件
```

---

## ❓ 常见问题

<details>
<summary><b><code>401 Invalid API key</code></b></summary>

请求缺少 `X-API-Key` 头，或密钥与 `ALICE_API_KEY` 环境变量不一致。默认值为 `alicesecret`。

</details>

<details>
<summary><b>Schema mismatch / 数据库表不存在</b></summary>

运行数据库迁移：

```bash
make migrate
# 或
docker compose exec api alembic upgrade head
```

</details>

<details>
<summary><b>Search 503</b></summary>

检查 Meilisearch 服务状态：

```bash
curl http://localhost:7700/health
```

</details>

<details>
<summary><b>Pipeline 卡在 <code>fetched</code></b></summary>

确认 worker 进程已启动且正在监听 `pipeline` 队列。查看 worker 日志：

```bash
docker compose logs -f worker
```

</details>

<details>
<summary><b>Bot 无响应</b></summary>

检查 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_WEBHOOK_HOST` 配置是否正确。Bot 需要公网可访问的 webhook 地址。

</details>

---

## ⚠️ 已知局限

> 当前版本为 **0.1.0 Early Beta**，以下为已知技术债与局限：

| 类别 | 详情 |
|:-----|:-----|
| 🔒 安全 | 默认 API Key 需在生产环境替换；Bot 端无用户鉴权 |
| 🧪 测试 | 部分集成测试仍使用 patch 隔离；前端 E2E 覆盖较薄 |
| 🤖 Gatekeeper | Ollama 不可用时存在规则回退路径 |
| 🔗 Legacy | `alice.worker.tasks` 保留旧任务名兼容 |
| 📊 排序 | 探索因子 ε 当前固定为 0.0 |
| 👥 多用户 | 前端当前硬编码 userId=1，多用户支持待完善 |
| 🕸️ GraphRAG | 语义搜索通道待实现 |

> 完整审计报告见 `AUDIT_REPORT.md`

---

## 📚 文档索引

| 文档 | 说明 |
|:-----|:-----|
| 📖 [README.md](README.md) | 英文版 — 项目概览与快速开始 |
| 🇨🇳 [README_ZH.md](README_ZH.md) | 本文档 — 中文版项目概览与快速开始 |
| 🏗️ [DESIGN.md](DESIGN.md) | 技术设计文档 — 架构细节与模块设计 |
| 🤝 [AGENTS.md](AGENTS.md) | 开发约定 — 工程原则与代码规范 |
| 🔍 [AUDIT_REPORT.md](AUDIT_REPORT.md) | 代码审计报告 — 技术债与改进建议 |
| 💡 [idea.md](idea.md) | 产品愿景 — 需求草案与未来规划 |

---

## 📊 Status

![Repobeats analytics](https://repobeats.axiom.co/api/embed/804172554acbfa044e815782ff8c848bde477070.svg "Repobeats analytics image")

---

<p align="center">
  <sub>🇨🇳 用户内容为中文 · 🇬🇧 代码与架构术语为英文</sub><br/>
  <sub>Built with ❤️ using FastAPI · Next.js · Neo4j · DeepSeek</sub>
</p>
