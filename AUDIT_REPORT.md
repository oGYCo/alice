# Alice — 全面代码库审计报告

**审计日期：** 2026-02-28  
**审计范围：** 全仓库（后端 Python 11,419 行、前端 TypeScript 8,264 行、测试 12,177 行、基础设施、迁移、文档）  
**分支：** main

---

## 1. 执行摘要

### 整体评估

Alice 是一个架构目标宏大的个人信息管理系统，实现了从 RSS/arXiv 采集到 Neo4j 知识图谱构建的完整 pipeline。项目在 **架构分层设计** 和 **功能广度** 方面表现突出——一个 0.1.0 版本拥有 20 个 service 模块、9 个 API 端点组、7 个前端页面、43 个测试文件（~300 用例），基础扎实。

然而，审计发现 **多处严重 Bug**（smoke_test.sh 无法运行、Alembic offline 模式崩溃）、**大量死代码和未集成实现**、以及 **系统性的一致性问题**（日志框架混用、事务边界不统一、URL 规范化三重实现）。这些问题如果不解决，将严重阻碍后续开发。

### 成熟度等级：**Early Beta — 核心可演示，但离生产部署仍有距离**

| 维度 | 评级 | 说明 |
|------|------|------|
| 架构设计 | ★★★★☆ | 分层清晰，LLM 抽象层优秀，Pipeline 设计合理 |
| 功能完整性 | ★★★☆☆ | 核心闭环可运行，但大量 Phase 2+ stub 和未集成实现 |
| 代码质量 | ★★★☆☆ | ruff 通过，但日志/事务/导入模式严重不一致 |
| 测试覆盖 | ★★★★☆ | 后端 35 个单元测试文件（7,833 行），集成测试 8 个文件 |
| 文档准确性 | ★★★☆☆ | 文档总体与实现对齐，但存在多处可验证偏差 |
| 生产就绪度 | ★★☆☆☆ | 安全默认值、脚本 Bug、资源泄漏需先修复 |
| 基础设施 | ★★☆☆☆ | 无 CI/CD、smoke_test 脚本损坏、Alembic env.py 有 Bug |

### 关键数字

| 指标 | 值 |
|------|---|
| Python 后端 | 11,419 行（63 个 .py 文件） |
| TypeScript 前端 | 8,264 行（77 个 .ts/.tsx 文件） |
| 测试代码 | 12,177 行（43 个测试文件） |
| Jinja2 模板 | 9 个 prompt 模板 |
| Alembic 迁移 | 6 个版本 |
| Docker 服务 | 8 个（api, bot, worker, scheduler, postgres, redis, meilisearch, neo4j） |

---

## 2. 代码库实际架构概览

### 2.1 真实架构图

```
                              ┌──────────────────────────────────────┐
                              │          Frontend (Next.js 16)       │
                              │  Feed │ Search │ Dashboard │ KG │ Settings │
                              └──────────────┬───────────────────────┘
                                             │ X-API-Key (cookie)
                              ┌──────────────▼───────────────────────┐
                              │       API Layer (FastAPI :8000)       │
                              │  APIKeyMiddleware → 9 Router Modules  │
                              └──┬────────┬────────┬────────┬────────┘
                                 │        │        │        │
                    ┌────────────▼─┐  ┌───▼────┐ ┌▼──────┐ │
                    │ 20 Services  │  │ Celery │ │ Bot   │ │
                    │ (business    │  │ Worker │ │(:8081)│ │
                    │  logic)      │  │        │ │       │ │
                    └──┬──┬──┬─────┘  └───┬────┘ └───┬───┘ │
                       │  │  │            │          │     │
              ┌────────▼┐ │  ▼            │          │     │
              │PostgreSQL│ │ Neo4j 5      │          │     │
              │   16     │ │ (KG)         │          │     │
              └──────────┘ │              │          │     │
                           ▼              │          │     │
                     Meilisearch ◄────────┘          │     │
                       v1.6                          │     │
                                                     │     │
                     Redis 7 ◄───────────────────────┘     │
                     (broker + state)                       │
                                                            │
                     Ollama ◄───── gatekeeper (local)       │
                     DeepSeek API ◄── understanding / scoring / extraction
```

### 2.2 Pipeline 数据流（实际实现）

```
Source → RSSConnector/ArxivConnector → store_raw (PG, URL dedup)
  → task_run_gatekeeper (Ollama → rule-based fallback)
    → task_run_understanding (DeepSeek)
      → task_run_graph_extraction (DeepSeek → Neo4j) [best-effort, 并行]
      → task_run_scoring (DeepSeek, 7-dim)
        → task_run_indexing (Meilisearch)
          → task_push_batch → Telegram Bot → User Feedback
            → KG Update → mastery 调整
```

**关键发现：**

- Pipeline 状态由各 task 自行管理，`PipelineOrchestrator` 完全未被调用（死代码）
- `task_fetch_all_sources` 实际在 `worker/tasks.py` 而非 `pipeline/tasks.py`
- 动态 Beat schedule（`get_dynamic_schedule`）已实现但未集成（死代码）
- SimHash 去重已实现但未集成到 pipeline（仅做 URL 精确匹配）

---

## 3. 严重发现（按优先级排序）

### P0 — 必须立即修复

#### 3.1 smoke_test.sh 完全无法运行

**文件：** `scripts/smoke_test.sh` 第 9 行

```bash
API_URL="http://localhost:8000"API_KEY="${ALICE_API_KEY:-alicesecret}"MAX_RETRIES=30
```

三个变量赋值没有换行分隔。Bash 将整行解析为一个赋值，导致：

- `API_URL` = `"http://localhost:8000API_KEY=alicesecretMAX_RETRIES=30"`
- `API_KEY` 和 `MAX_RETRIES` 永远未定义
- **脚本在首次引用 `$MAX_RETRIES` 时因 `set -u` 崩溃**

**修复：** 已在本次审计中同步修复（拆分为独立行）。

#### 3.2 Alembic env.py offline 模式崩溃

**文件：** `alembic/env.py` 第 55 行

```python
is_autogenerate = context.is_autogenerate
```

`alembic.context.EnvironmentContext` **没有** `is_autogenerate` 属性。`run_migrations_offline()` 被调用时抛出 `AttributeError`。

**修复：** 已在本次审计中同步修复（删除不存在属性的引用，使用 `literal_binds=True`）。

#### 3.3 Alembic autogenerate 功能完全失效

**文件：** `alembic/env.py` 第 92-95 行

```python
if "--autogenerate" in sys.argv or "revision" in sys.argv:
    run_migrations_offline()
```

`alembic revision --autogenerate` 需要在线连接数据库对比 schema。强制走 offline 模式使 autogenerate **完全无法检测模型与数据库差异**。

**修复：** 已在本次审计中同步修复（删除 autogenerate 强制离线逻辑）。

---

### P1 — 高优先级

#### 3.4 task_run_scoring 重试前标记 failed

**文件：** `src/alice/pipeline/tasks.py`

`task_run_scoring` 在调用 `self.retry(exc=exc)` **之前** 将状态设为 `PipelineStatus.failed`。重试时内容已处于 failed 状态，可能导致与 `task_retry_failed` 的竞态。对比 `task_run_understanding` 仅在 `retries >= max_retries` 时才标记 failed——两个 task 处理错误的方式不一致。

#### 3.5 Content.simhash 列类型 32 位溢出

**文件：** `src/alice/models/content.py` + `alembic/versions/b1c2d3e4f5g6_*.py`

模型声明 `simhash = Column(Integer)`，但 `DeduplicationService.compute_simhash()` 返回 64 位整数。PostgreSQL `Integer` 为 32 位（max 2^31-1），高位截断会导致假阳性碰撞率暴增。应改用 `BigInteger`。

#### 3.6 Worker legacy wrapper 同步执行而非 dispatch

**文件：** `src/alice/worker/tasks.py`

```python
def task_run_gatekeeper(content_id: int):
    real_task = _tasks_module.task_run_gatekeeper
    return real_task(content_id)  # 应该是 real_task.delay(content_id)
```

Legacy wrapper 直接调用 task 函数而非 `.delay()`，任务在同一 worker 进程中同步执行而非分发到队列。

#### 3.7 Neo4j 密码解析假设不含 `/`

**文件：** `src/alice/pipeline/tasks.py`

```python
settings.NEO4J_AUTH.split("/", 1)
```

如果密码包含 `/`（完全合法），解析会截取错误的 user/password。

#### 3.8 前端 15+ 处硬编码 `userId = 1`

**文件：** `frontend/src/lib/api.ts`（8 处）、`frontend/src/components/settings/`（6 处）、`KnowledgeGraph.tsx`（1 处）

所有 API 调用使用 `userId = 1` 默认值，使多用户支持成为不可能。应从 auth store 统一获取。

#### 3.9 URL 规范化三重实现且行为不一致

| 文件 | 去除的参数 |
|------|-----------|
| `services/dedup.py` | utm_*, fbclid, gclid, msclkid, ref, referrer, source |
| `services/storage.py` | utm_* only |
| `connectors/rss.py` | utm_* + 额外 tracking 参数 |

同一 URL 在不同代码路径可能被判为不同/相同内容。应统一为 `DeduplicationService.normalize_url()` 一个入口。

#### 3.10 PushService 每次调用创建 6 个新 service 实例

**文件：** `src/alice/services/push.py`

`PushService.__init__` 和 `get_next_push_batch` 每次创建 `MatchingService`、`RankingService`、`GraphRAGQueryEngine` 等新实例。在定时任务 20 分钟一次的场景下，每次推送都会创建新的 Neo4j 连接、新的 httpx 客户端等。应使用依赖注入或缓存。

---

### P2 — 中期技术债

#### 3.11 PipelineOrchestrator 是完全的死代码

`pipeline/orchestrator.py` 定义了 `advance_pipeline()` 和 `process_new_content()` 方法，但 `pipeline/tasks.py` 中每个 task 都自行管理状态转换。orchestrator 从未被实例化或调用。

#### 3.12 日志框架全局不一致

| 模块 | 日志方式 |
|------|---------|
| `graph/*`, `services/community_detection`, `services/dedup` 等 | structlog (cast to `_Logger` Protocol) |
| `connectors/rss.py`, `services/push.py` | structlog (直接使用) |
| `llm/deepseek.py`, `llm/ollama.py` | stdlib `logging.getLogger` |
| `pipeline/tasks.py`, `worker/*` | stdlib `logging.getLogger` |
| `bot/handlers/*` | stdlib `logging.getLogger` |
| `services/review_service.py` | stdlib `logging.getLogger` |
| `connectors/arxiv.py` | **无日志** |

项目声称使用 structlog，但超过一半模块使用 stdlib logging。arXiv connector 完全无日志。

#### 3.13 事务边界无统一策略

| 文件 | 模式 | 问题 |
|------|------|------|
| `services/source_service.py` | 每方法 `commit()` | 调用方无法组合事务 |
| `services/review_service.py` | 每方法 `flush()` | 需要调用方 `commit()` |
| `services/storage.py` | 混合（store_raw commit, 其他 commit） | 不一致 |
| `services/memory_system.py` | 每方法 `commit()` | 与 review_service 不同 |

无统一契约，新开发者很容易引入数据一致性 bug。

#### 3.14 TanStack Query — 已安装完全未使用

`@tanstack/react-query ^5.90.21` 声明为前端生产依赖，但整个 `frontend/src/` 零引用。所有 API 调用使用 `useEffect` + `useState` 手写。增加 ~40KB gzip bundle 体积，且无请求缓存/去重/后台刷新能力。

#### 3.15 importlib 动态导入散布多处

| 文件 | 导入数 |
|------|--------|
| `main.py` | 9 个 router module |
| `services/gatekeeper.py` | structlog, prompts, schemas |
| `api/v1/connectors.py` | connectors, schemas |

完全破坏 IDE 类型追踪、重构工具和 import graph 分析。无文档说明使用原因。

#### 3.16 N+1 查询风险

| 文件 | 位置 | 最坏情况 |
|------|------|---------|
| `api/v1/dashboard.py` `_learning_velocity` | 8 次单独 COUNT 查询 |
| `api/v1/dashboard.py` `_review_schedule` streak | 最多 365 次单独 COUNT 查询 |
| `services/community_detection.py` `update_community_labels` | N 次单独 Cypher 写入 |
| `services/matching.py` `_query_shortest_distance` | N 次单独 Cypher 查询 |

#### 3.17 LLM 客户端资源泄漏

- `LLMClient` Protocol 无 `close()` 方法
- `ollama.py` 的 httpx 客户端有 `close()` 方法但无人调用
- `pipeline/tasks.py` 每次创建 `OllamaClient` / `Bot` 新实例，连接不会关闭
- `deepseek.py` 使用 OpenAI SDK 客户端，同样无生命周期管理

#### 3.18 `_Logger` Protocol 重复定义 10+ 处

`graph/client.py`、`graph/extractor.py`、`graph/repository.py`、`graph/user_kg.py`、`services/community_detection.py`、`services/dedup.py`、`services/graphrag_query.py`、`services/kg_updater.py`、`services/matching.py`、`services/memory_system.py` 各自定义了完全相同的 `_Logger` Protocol。

#### 3.19 Ollama 客户端无重试逻辑

`deepseek.py` 有 3 次重试 + 退避策略和 JSON 解析重试。`ollama.py` 的 `complete()` 和 `complete_structured()` 完全无重试，网络抖动直接失败。

---

## 4. 未完成 / 缺失功能明细

### 4.1 Stub / 占位实现

| 位置 | 内容 | 状态 |
|------|------|------|
| `services/graphrag_query.py` `_semantic_search()` | 永远返回 `[]` | Phase 2 stub |
| `services/skill_executor.py` | 非 KG/非 self_review 技能返回 `{"note": "stub_execution"}` | 未实现 |
| `bot/handlers/commands.py` `/settings` | 返回"即将推出" | 占位 |
| `bot/handlers/commands.py` `/status` | 硬编码状态 | 占位 |
| `bot/handlers/feedback.py` `handle_explain_concept` | "Phase 4" 占位 | 未实现 |
| `bot/handlers/feedback.py` `handle_discuss` | "Phase 4" 占位 | 未实现 |
| `services/ranking.py` `epsilon_explore = 0.0` | 硬编码 | 探索因子未实现 |
| `graph/repository.py` `get_content_subgraph` mastery | 硬编码 `0.5` | 未接入 user mastery |
| `services/push_scheduler.py` `timezone` 字段 | 声明但从未使用 | 时区支持未实现 |

### 4.2 已实现但未集成

| 功能 | 描述 | 完成度 |
|------|------|--------|
| SimHash 去重 | `DeduplicationService` 有完整 SimHash 实现，但 pipeline 不调用 | 实现未集成 |
| 动态 Beat Schedule | `get_dynamic_schedule` 可从 DB 读取源调度间隔 | 实现未集成 |
| `PushModifiers` | `pause_non_related` 和 `lightweight_only` 字段未被 ranking/push 检查 | 声明未消费 |
| `scoring.reasoning` 存储 | `update_score` 接收 `reasoning` 参数但 DB 无对应列 | 实现不完整 |
| `save_for_later` 反馈 | `kg_updater` 对此类型直接 `pass` | 未实现 |
| RateLimiter | `bot/handlers/push.py` 中已实现但 `send_push` 未使用 | 实现未集成 |
| Bot 用户鉴权 | 任何 Telegram 用户可使用 bot | 未实现 |

### 4.3 死代码

| 位置 | 内容 |
|------|------|
| `pipeline/orchestrator.py` | 整个 `advance_pipeline` 和 `process_new_content` |
| `pipeline/scheduler.py` | `get_dynamic_schedule()` |
| `pipeline/tasks.py` | `_get_storage()` 和 `_fail_content()` helper |
| `services/fsrs_engine.py` | `get_due_cards_filter()` |
| `services/user_state.py` | `auto_detect_mode()` |
| `worker/tasks.py` | `task_push_batch` legacy wrapper（功能性缺失） |
| `frontend/src/lib/store.ts` | `useSidebarStore.width`, `activeSourceId` |
| `frontend/src/lib/types.ts` | `ContentItem.url`, `ApiError` 类型 |
| `frontend/src/components/content/AIAnalysis.tsx` | `DomainsCard` 导出未使用 |

---

## 5. 文档审计

### 5.1 README.md 偏差（已修复）

| 位置 | 声称 | 实际 | 状态 |
|------|------|------|------|
| Frontend 技术栈表 | 包含 TanStack Query | TanStack Query **完全未使用** | ✅ 已修复 |
| Pipeline Fetch 阶段 | "URL normalization" | SimHash **未集成** pipeline，仅做 URL 精确匹配 | ✅ 已改写 |
| 定时任务小节 | "Each source also has its own dynamic schedule" | `get_dynamic_schedule` 是**死代码**，使用硬编码 schedule | ✅ 已修复 |
| Backend 技术栈 | "structlog (JSON)" | 半数模块使用 stdlib logging | ✅ 已修改为 mixed |

### 5.2 DESIGN.md 偏差

| 位置 | 声称 | 实际 |
|------|------|------|
| §3.3 Pipeline 任务层 | "状态持久化到 PostgreSQL，支持故障恢复" | `task_run_scoring` 在重试前错误标记 failed |
| §8 新模块接入规范 | "配置项需同步更新 .env.example" | 项目内多处新增未更新 .env.example |

### 5.3 AGENTS.md 偏差（已修复）

| 位置 | 声称 | 实际 | 状态 |
|------|------|------|------|
| Pipeline 小节 | "Active stage tasks: `alice.pipeline.tasks`" | `task_fetch_all_sources` 实际在 `alice.worker.tasks` | ✅ 已修复 |

### 5.4 缺失的文档

| 缺失项 | 影响 |
|--------|------|
| CI/CD 配置 | 无 GitHub Actions / GitLab CI 等自动化流程 |
| 贡献指南 (CONTRIBUTING.md) | 新开发者无入门指引 |
| 变更日志 (CHANGELOG.md) | 无版本变更记录 |
| 部署指南（生产环境） | README 只有开发环境部署 |
| 监控/告警配置 | 无可观测性文档 |

---

## 6. 技术债清单

### 6.1 高影响

| # | 债项 | 位置 | 长期后果 |
|---|------|------|---------|
| 1 | smoke_test.sh 变量赋值 Bug | `scripts/smoke_test.sh:9` | CI smoke test 完全无法运行 — **已修复** |
| 2 | Alembic env.py 双 Bug | `alembic/env.py:55,92` | 离线迁移崩溃 + autogenerate 失效 — **已修复** |
| 3 | 事务边界不统一 | services 层整体 | 数据一致性风险 |
| 4 | URL 规范化三重实现 | 3 个文件 | 去重不一致导致重复/漏检 |
| 5 | 日志框架混用 | 全项目 | 无法统一日志格式/过滤/采集 |

### 6.2 中等影响

| # | 债项 | 位置 | 长期后果 |
|---|------|------|---------|
| 6 | importlib 动态导入 | main.py, gatekeeper.py 等 | IDE/类型检查失效 |
| 7 | PipelineOrchestrator 死代码 | pipeline/orchestrator.py | 误导新开发者 |
| 8 | LLMClient 无生命周期管理 | protocol.py, factory.py | HTTP 连接泄漏 |
| 9 | 前端大文件 | search/page (706行), KG (723行) | 可维护性差 |
| 10 | 前端硬编码 userId=1 | ~15 处 | 多用户支持需大面积修改 |
| 11 | TanStack Query 死依赖 | package.json | bundle 膨胀 ~40KB |
| 12 | `_Logger` Protocol 10+ 重复 | graph/*, services/* | DRY 违反 |
| 13 | 枚举重复定义 | models vs schemas | 类型系统不严谨 |
| 14 | `NodeLabel`/`RelType` 非 Enum | graph/schema.py | 无类型安全 |

### 6.3 低影响

| # | 债项 | 位置 |
|---|------|------|
| 15 | Alembic revision ID 格式不规范 | alembic/versions/ (含 g, h 非十六进制字符) |
| 16 | ArxivConnector 使用弃用 `asyncio.get_event_loop()` | connectors/arxiv.py |
| 17 | ArxivConnector 完全无日志 | connectors/arxiv.py |
| 18 | `__init__.py` 未导出 ArxivConnector | connectors/__init__.py |
| 19 | `getApiKey()` 在请求中可能调用两次 | frontend/src/lib/api.ts |
| 20 | 前端 `heatmapMode` dead branch | ConceptNode.tsx |
| 21 | 前端重复常量/工具函数 | formatTimeAgo, CONTENT_TYPE_LABELS 等 |
| 22 | `next-themes` 安装未使用 | frontend/package.json |

---

## 7. 测试覆盖审计

### 7.1 后端测试概要

| 类型 | 文件数 | ~行数 | 质量 |
|------|--------|-------|------|
| 单元测试 | 35 | 7,833 | ★★★★☆ 行为覆盖好，mock 层次合理 |
| 集成测试 | 8 | 2,690 | ★★★★☆ 真实 DB/图谱依赖 |

### 7.2 未覆盖的高风险后端模块

| 模块 | 风险 | 原因 |
|------|------|------|
| `services/review_service.py` | 🔴 高 | FSRS 复习卡片服务**完全无测试** |
| `llm/deepseek.py` | 🔴 高 | 主 LLM 客户端无直接测试 |
| `llm/ollama.py` | 🔴 高 | Gatekeeper LLM 客户端无直接测试 |
| `api/v1/content.py` | 🟡 中 | 最常用 CRUD 端点无路由级测试 |
| `api/v1/dashboard.py` | 🟡 中 | N+1 查询逻辑未验证 |
| `api/v1/pipeline.py` | 🟡 中 | Pipeline 控制端点无测试 |
| `api/v1/kg.py` | 🟡 中 | KG API 含 Cypher 注入风险，无测试 |
| `bot/main.py` | 🟡 中 | Webhook 注册逻辑无测试 |

### 7.3 前端测试概要

| 类型 | 文件数 | ~行数 | 质量 |
|------|--------|-------|------|
| Vitest 单元 | 17 | ~1,700 | ★★★☆☆ 中等 |
| Playwright E2E | 3+1 | ~250 | ★★☆☆☆ 极弱 |

**前端关键缺失：**

- Search 页（706 行最复杂页面）无专门测试
- Login 页无测试
- AuthGuard 无测试
- Zustand stores 无直接测试
- 无全局 `error.tsx` / `not-found.tsx`

---

## 8. 安全与可靠性

### 8.1 安全问题

| # | 问题 | 严重性 |
|---|------|--------|
| 1 | Bot 无用户白名单 — 任何人可操作 | 🟡 中 |
| 2 | API Key 默认 `alicesecret`，生产易遗漏更换 | 🟡 中 |
| 3 | Meilisearch 默认 `masterKey`，直接暴露在 docker-compose | 🟡 中 |
| 4 | Neo4j 密码硬编码在 docker-compose.yml | 🟢 低 |
| 5 | `user_kg.py` 直接拼 Cypher 查询，绕过 repository 校验层 | 🟡 中 |

### 8.2 可靠性问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | `deliver_push` 统一 commit | 中途失败导致已推内容不标记 pushed_at |
| 2 | `task_retry_failed` 无最大重试次数 | 永久失败内容无限重试 |
| 3 | 反馈不幂等 | 用户多次点击创建多条重复记录 |
| 4 | `RateLimiter` 仅进程内存 | 多实例部署下失效 |
| 5 | `get_shared_graph_client` 无并发保护 | 多协程可能泄漏连接 |

---

## 9. Prompt 模板审计

| 模板 | 状态 | 问题 |
|------|------|------|
| `gatekeeper.j2` | ✅ 正常 | — |
| `understanding.j2` | ✅ 正常 | — |
| `quality_score.j2` | ✅ 正常 | 1-10 分制 |
| `quality_score_7d.j2` | ⚠️ 变量名不一致 | 使用 `content_title`/`content_text` 而非项目标准 `title`/`text` |
| `push_card.j2` / `push_card_en.j2` | ✅ 正常 | — |
| `push_enrichment.j2` | ✅ 正常 | — |
| `push_reason.j2` | ✅ 正常 | — |
| `extract_subgraph.j2` | ✅ 正常 | — |

**额外发现：** 两套评分模板共存（`quality_score.j2` 用 1-10 分制，`quality_score_7d.j2` 用 7 维度 JSON），输出格式不兼容。`PromptManager` 缺少 `quality_score_7d`、`extract_subgraph`、`push_card` 的便捷方法。

---

## 10. 可执行建议（按优先级）

### 立即修复（本周）

| # | 行动 | 工作量 | 影响 |
|---|------|--------|------|
| 1 | ~~修复 `smoke_test.sh` 变量赋值换行~~ | 5min | ✅ 已完成 |
| 2 | ~~修复 `alembic/env.py` 双 Bug~~ | 30min | ✅ 已完成 |
| 3 | 统一 URL 规范化到 `DeduplicationService.normalize_url()` | 2h | 去重一致性 |
| 4 | 修复 `task_run_scoring` 的 failed 标记时机 | 30min | 重试正确性 |
| 5 | `Content.simhash` 改用 `BigInteger` + 新迁移 | 30min | 数据正确性 |

### 短期改进（2 周内）

| # | 行动 | 工作量 | 影响 |
|---|------|--------|------|
| 6 | 统一日志到 structlog | 4h | 一致性 + 可观测性 |
| 7 | 建立统一事务管理策略 | 4h | 数据一致性 |
| 8 | 清理所有 importlib 动态导入 | 3h | 可维护性 |
| 9 | 删除确认的死代码 | 3h | 代码卫生 |
| 10 | 添加 `review_service` 测试 | 3h | 测试覆盖 |

### 中期改进（1-2 月）

| # | 行动 | 工作量 | 影响 |
|---|------|--------|------|
| 11 | 前端移除或正式迁移到 TanStack Query | 8h | 代码质量 + UX |
| 12 | 消除前端硬编码 userId=1 | 4h | 多用户支持 |
| 13 | 建立 CI pipeline (lint + test + type check) | 4h | 质量门禁 |
| 14 | 补齐 API 端点测试 | 8h | 测试覆盖 |
| 15 | 前端 E2E 测试重写 | 6h | 质量门禁 |
| 16 | LLMClient 添加 `close()` + 上下文管理 | 2h | 资源管理 |
| 17 | 拆分前端大文件 | 4h | 可维护性 |
| 18 | Dashboard 查询优化 | 3h | 性能 |

### 长期架构改进

| # | 行动 |
|---|------|
| 19 | 引入依赖注入，消除 service 层手动实例化 |
| 20 | 建立多用户支持（user context 贯穿全栈） |
| 21 | 添加可观测性（OpenTelemetry + Prometheus） |
| 22 | 生产部署指南（TLS, 密钥管理, 备份） |

---

*审计完成。本报告基于对仓库内全部源文件（63 个 Python 文件、77 个 TypeScript/TSX 文件、6 个迁移文件、9 个 Jinja2 模板、5 个文档、7 个配置文件）的逐文件分析生成。*
