# Alice — 全面代码库审计报告

**审计日期：** 2026-02-28  
**审计范围：** 全仓库（后端 Python、前端 Next.js、基础设施、测试、文档）  
**分支：** main

---

## 1. 执行摘要

### 整体评估

Alice 是一个有雄心的个人信息管理系统，具备从信息采集到知识图谱构建的完整 pipeline。项目在 **架构设计** 和 **功能完整性** 方面表现出色 —— 一个 0.1.0 版本拥有 20 个 service 模块、9 个 API 端点组、6 个前端页面、300+ 个测试用例，是相当扎实的基础。

P1/P2 技术债需按优先级逐步清理。

### 成熟度等级：**早期 Beta**

| 维度 | 评级 | 说明 |
|------|------|------|
| 架构设计 | ★★★★☆ | 分层清晰，LLM 抽象层设计优秀 |
| 功能完整性 | ★★★★☆ | 核心闭环可运行，但多处 Phase 2+ stub |
| 代码质量 | ★★★☆☆ | 风格不一致，死代码积累，中文支持缺陷 |
| 测试覆盖 | ★★★★☆ | 后端优秀（300+ 用例），前端 E2E 极弱 |
| 文档准确性 | ★★★★☆ | 文档纪律较好，少量偏差 |
| 生产就绪度 | ★★☆☆☆ | 安全默认值、资源泄漏、阻塞 IO 需先修复 |

---

## 2. 代码库实际架构概览

### 2.1 真实架构图

```
                              ┌──────────────────────────────────────┐
                              │           Frontend (Next.js 16)      │
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
                     (broker)                               │
                                                            │
                     Ollama ◄───────────────────────────────┘
                     (gatekeeper)
                     
                     DeepSeek API ◄── understanding / scoring / extraction
```

### 2.2 关键数据流

```
Source → RSSConnector/ArxivConnector → store_raw (PG)
  → task_run_gatekeeper (Ollama/rule-based)
    → task_run_understanding (DeepSeek)
      → task_run_graph_extraction (DeepSeek → Neo4j)  [best-effort, 并行]
      → task_run_scoring (DeepSeek)
        → task_run_indexing (Meilisearch)
          → task_push_batch → Telegram Bot → User Feedback
            → KG Update → mastery 调整
```

### 2.3 实际子系统交互矩阵

| 调用方 \ 被调用方 | PG | Redis | Neo4j | Meilisearch | DeepSeek | Ollama | Telegram |
|---|---|---|---|---|---|---|---|
| API Layer | ✅ | — | ✅ (best-effort) | ✅ | — | — | — |
| Pipeline Tasks | ✅ | ✅ (broker) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Bot Handlers | ✅ | — | — | — | — | — | ✅ (send) |
| Worker/Scheduler | — | ✅ (beat) | — | — | — | — | — |

---

## 3. 严重发现（按优先级排序）

### P1 — 短期必须修复

#### 3.8 Pipeline 状态机在 retry 后不一致

| 文件 | 问题 |
|------|------|
| [pipeline/tasks.py](src/alice/pipeline/tasks.py) | `task_run_understanding` 先将状态设为 `failed`，然后 `raise self.retry()` |

当 Celery retry 触发时，DB 中状态已经是 `failed`。但 retry 的 task 会重新读取内容，此时需要的前置状态是 `gatekept`。如果有其他代码依赖 `pipeline_status == 'gatekept'` 来判断是否应该执行 understanding，retry 会被跳过。

#### 3.9 三重冗余的 Beat Schedule

| 文件 | 描述 |
|------|------|
| [worker/celery_app.py](src/alice/worker/celery_app.py) | 实际使用的 schedule（硬编码） |
| [pipeline/scheduler.py](src/alice/pipeline/scheduler.py) | 相似但不同的 schedule 定义（死代码） |
| [worker/scheduler.py](src/alice/worker/scheduler.py) | 另一份 schedule 定义（死代码） |

三份独立维护的 schedule，只有 `celery_app.py` 中的实际生效。`task_retry_failed_graph_extractions` 只在 `celery_app.py` 中存在。**极易在修改时只更新一处导致不同步。**

#### 3.10 推送计数未按 user_id 过滤

| 文件 | 位置 |
|------|------|
| [pipeline/tasks.py](src/alice/pipeline/tasks.py) | `task_schedule_push_batches` |

`Content.pushed_at >= today_start` 的 COUNT 没有 `WHERE user_id = ?` 过滤。多用户场景下，所有用户共享推送计数，当用户 A 的推送耗尽额度后，用户 B 也无法收到推送。

#### 3.11 OllamaClient 每次请求创建新 HTTP 客户端

| 文件 | 问题 |
|------|------|
| [llm/ollama.py](src/alice/llm/ollama.py) | `complete()` 和 `complete_structured()` 内部每次 `async with httpx.AsyncClient(...)` |

无连接复用，每次 gatekeeper 评估都建立新 TCP 连接。在高吞吐场景下成为性能瓶颈。

#### 3.12 KG Updater 查询全局 mastery 而非 user-specific

| 文件 | 问题 |
|------|------|
| [services/kg_updater.py](src/alice/services/kg_updater.py) | `_get_content_concepts` 的 Cypher 查询 `concept.mastery` 是节点属性（全局），但 `update_mastery` 更新的是 `(User)-[KNOWS]->(Concept)` 关系上的 mastery（user-specific） |

导致反馈处理时，增量计算基于错误的 baseline mastery。

#### 3.13 前端 LoginPage 缺少 Suspense

| 文件 | 问题 |
|------|------|
| [frontend/src/app/(auth)/login/page.tsx](frontend/src/app/(auth)/login/page.tsx) | `useSearchParams()` 在无 Suspense boundary 的 client component 中使用 |

Next.js App Router 要求 `useSearchParams` 必须有 Suspense boundary，否则生产构建会报错。

---

### P2 — 中期技术债

#### 3.14 N+1 查询问题

| 文件 | 位置 | 最坏情况 |
|------|------|------|
| [api/v1/dashboard.py](src/alice/api/v1/dashboard.py) | `_learning_velocity` | 8 次单独 COUNT 查询 |
| [api/v1/dashboard.py](src/alice/api/v1/dashboard.py) | `_review_schedule` streak 计算 | 最多 365 次单独 COUNT 查询 |
| [services/community_detection.py](src/alice/services/community_detection.py) | `update_community_labels` | N 次单独 Cypher 写入 |
| [services/matching.py](src/alice/services/matching.py) | `_query_shortest_distance` | N 次单独 Cypher 查询 |

#### 3.15 事务边界不统一

| 文件 | 模式 | 问题 |
|------|------|------|
| [services/source_service.py](src/alice/services/source_service.py) | 每方法 `commit()` | 调用方无法组合事务 |
| [services/review_service.py](src/alice/services/review_service.py) | 每方法 `flush()` | 需要调用方 `commit()`——不一致 |
| [services/storage.py](src/alice/services/storage.py) | 混合（store_raw commit, update_* flush） | 部分设计陷阱 |
| [services/memory_system.py](src/alice/services/memory_system.py) | 每方法 `commit()` | 与 review_service 不同 |

无统一策略，新开发者很容易误用。

#### 3.16 URL 规范化逻辑重复且行为不一致

| 文件 | 去除的参数 |
|------|------|
| [services/dedup.py](src/alice/services/dedup.py) | `utm_*`, `fbclid`, `gclid`, `ref`, `source`, `ref_src`, `ref_url` |
| [services/storage.py](src/alice/services/storage.py) | `utm_*` only |
| [connectors/rss.py](src/alice/connectors/rss.py) | `utm_*` + 额外 tracking 参数 |

三份独立的 URL 规范化实现，清理的参数集不同。

#### 3.17 Orchestrator 与实际 Task 实现脱节

| 文件 | 状态 |
|------|------|
| [pipeline/orchestrator.py](src/alice/pipeline/orchestrator.py) | `advance_pipeline` 和 `process_new_content` 完整实现 |
| [pipeline/tasks.py](src/alice/pipeline/tasks.py) | 每个 task 自行管理状态转换，不调用 orchestrator |

Orchestrator 存在但未被使用，是死代码。

#### 3.18 TanStack Query 已安装但完全未使用

| 文件 | 问题 |
|------|------|
| [frontend/package.json](frontend/package.json) | `@tanstack/react-query` 在依赖中 |
| 所有前端页面 | 使用 `useState` + `useEffect` 手写 API 调用 |

导致：无请求缓存、无去重、无后台刷新、无乐观更新、大量 loading/error 样板代码。

#### 3.19 importlib 动态导入散布多处

| 文件 | 位置 |
|------|------|
| [main.py](src/alice/main.py) | 所有 API router 导入（9个） |
| [services/gatekeeper.py](src/alice/services/gatekeeper.py) | structlog, prompts, schemas |
| [api/v1/connectors.py](src/alice/api/v1/connectors.py) | connectors, schemas |
| 多个测试文件 | test_gatekeeper, test_rss_connector |

没有文档说明使用 `importlib` 的原因，破坏 IDE 类型追踪和 import graph 分析。

---

## 4. 未完成 / 缺失功能明细

### 4.1 明确的 Stub / 占位实现

| 位置 | 内容 | 状态 |
|------|------|------|
| [services/graphrag_query.py](src/alice/services/graphrag_query.py) | `_semantic_search()` 永远返回 `[]` | Phase 2 stub |
| [services/skill_executor.py](src/alice/services/skill_executor.py) | 非 KG / 非 self_review 的技能返回 `{"note": "stub_execution"}` | 未实现 |
| [bot/handlers/commands.py](src/alice/bot/handlers/commands.py) | `/settings` 返回"即将推出" | 占位 |
| [bot/handlers/commands.py](src/alice/bot/handlers/commands.py) | `/status` 返回硬编码状态 | 占位 |
| [bot/handlers/feedback.py](src/alice/bot/handlers/feedback.py) | `handle_explain_concept` → "Phase 4" 占位 | 未实现 |
| [bot/handlers/feedback.py](src/alice/bot/handlers/feedback.py) | `handle_discuss` → "Phase 4" 占位 | 未实现 |
| [services/ranking.py](src/alice/services/ranking.py) | `epsilon_explore = 0.0` 硬编码 | 探索因子未实现 |
| [graph/repository.py](src/alice/graph/repository.py) | `get_content_subgraph` 的 mastery 硬编码 `0.5` | 未接入 user mastery |
| [services/push_scheduler.py](src/alice/services/push_scheduler.py) | `timezone` 字段声明但从未使用 | 时区支持未实现 |

### 4.2 死代码

| 位置 | 内容 |
|------|------|
| [pipeline/orchestrator.py](src/alice/pipeline/orchestrator.py) | 整个 `advance_pipeline` 方法 |
| [pipeline/scheduler.py](src/alice/pipeline/scheduler.py) | `get_dynamic_schedule()` 函数 |
| [pipeline/scheduler.py](src/alice/pipeline/scheduler.py) + [worker/scheduler.py](src/alice/worker/scheduler.py) | 两个完整的 scheduler 模块（未被导入） |
| [pipeline/tasks.py](src/alice/pipeline/tasks.py) | `_get_storage()` 和 `_fail_content()` helper |
| [services/fsrs_engine.py](src/alice/services/fsrs_engine.py) | `get_due_cards_filter()` |
| [services/user_state.py](src/alice/services/user_state.py) | `auto_detect_mode()` |
| [worker/tasks.py](src/alice/worker/tasks.py) | `task_push_batch` legacy wrapper（故意断裂） |
| [frontend/src/lib/store.ts](frontend/src/lib/store.ts) | `useSidebarStore.width`, `activeSourceId` |
| [frontend/src/lib/types.ts](frontend/src/lib/types.ts) | `ContentItem.url`, `ApiError` |
| [frontend/src/components/content/AIAnalysis.tsx](frontend/src/components/content/AIAnalysis.tsx) | `DomainsCard` 导出但未使用 |

### 4.3 缺失的功能 / 集成点

| 功能 | 描述 | 完成度 |
|------|------|------|
| SimHash 去重集成 | `DeduplicationService` 有 SimHash 实现但未被 pipeline 调用 | 实现未集成 |
| 动态 Beat Schedule | `get_dynamic_schedule` 可从 DB 读取源的调度间隔 | 实现未集成 |
| `PushModifiers` 消费 | `pause_non_related` 和 `lightweight_only` 字段在 ranking/push 中从未被检查 | 声明未消费 |
| `scoring.reasoning` 存储 | `update_score` 接收 `reasoning` 参数但未写入 DB（缺列） | 实现不完整 |
| `save_for_later` 反馈处理 | `kg_updater` 对此反馈类型直接 `pass` | 未实现 |
| KG mismatch 分析结果 | `_adjust_preferences` 中 LLM 分析结果被丢弃 | 计算但未存储 |
| 速率限制器集成 | `RateLimiter` 已定义但 `send_push` 未使用 | 实现未集成 |
| 多用户支持 | 前端硬编码 `userId=1`，推送计数无 user_id 过滤 | 架构上支持但实现不完整 |
| Bot 用户鉴权 | 任何 Telegram 用户可使用 bot | 未实现 |

---

## 5. 文档审计

### 5.1 准确的文档

| 文档 | 评价 |
|------|------|
| [AGENTS.md](AGENTS.md) | ✅ 准确且内容丰富，与代码一致 |
| [DESIGN.md](DESIGN.md) | ✅ 有明确的"实现对齐版"标签，区分已实现 vs Roadmap |
| [idea.md](idea.md) | ✅ 明确标注为愿景文档，不声称实现状态 |
| [.env.example](.env.example) | ✅ 变量齐全，默认值合理 |

### 5.2 文档偏差

| 文档 | 偏差点 | 实际情况 |
|------|------|------|
| [README.md](README.md) | "状态管理: Zustand + TanStack Query" | TanStack Query 已安装但**完全未使用** |
| [README.md](README.md) | "Fetch 阶段: URL 归一化 + SimHash 去重" | SimHash 去重**未集成**到 pipeline，仅做 URL 精确匹配 |
| [README.md](README.md) | "各数据源还有独立的动态调度" | `get_dynamic_schedule` 是**死代码**，实际使用硬编码 beat schedule |
| [README.md](README.md) | "日志: structlog（JSON 结构化）" | 部分模块使用标准 `logging` 而非 `structlog` |
| [DESIGN.md](DESIGN.md) | 第 5 条 "新模块接入规范" 要求含 `.env.example` 更新 | 其他规范均好，但此文档版本遵循情况一般 |
| [AGENTS.md](AGENTS.md) | "Pipeline -- Active stage tasks: `alice.pipeline.tasks`" | `task_fetch_all_sources` 实际在 `alice.worker.tasks` 中，不在 pipeline 模块 |

### 5.3 缺失的文档

| 缺失项 | 影响 |
|------|------|
| CI/CD 配置 | 无 GitHub Actions / GitLab CI 等自动化流程 |
| 贡献指南 | 无 CONTRIBUTING.md |
| 变更日志 | 无 CHANGELOG.md |
| API 错误码文档 | 仅依赖 FastAPI 自动生成文档 |
| 部署指南（生产环境） | README 只有 Docker Compose 开发部署 |
| 监控 / 告警配置 | 无可观测性文档（metrics / tracing / alerting） |

---

## 6. 技术债清单

### 6.1 高影响技术债

| # | 债项 | 位置 | 长期后果 |
|---|------|------|------|
| 4 | 推送编排每次 new instance | push.py | 6 个服务类每次调用重新实例化，性能差、状态不一致 |
| 5 | 三重 schedule 冗余 | 3 个文件 | 修改时很容易遗漏导致行为不一致 |
| 6 | 事务边界无统一契约 | services 层 | 新开发者容易引入数据一致性 bug |
| 7 | URL 规范化三重实现 | 3 个文件 | 同一 URL 在不同路径可能被判为不同/相同 |

### 6.2 中等影响技术债

| # | 债项 | 位置 | 长期后果 |
|---|------|------|------|
| 8 | importlib 动态导入 | main.py, gatekeeper.py, 等 | IDE/类型检查/重构工具失效 |
| 9 | logging 库不统一 | 多个模块 | 日志格式和过滤不一致 |
| 10 | DeepSeek prompt 累积 | deepseek.py complete_structured | 多次重试后 prompt 膨胀可能超限 |
| 11 | LLMClient 无 close() 方法 | protocol.py | HTTP 客户端资源泄漏 |
| 12 | front 大文件（700+ 行） | search/page.tsx, KnowledgeGraph.tsx | 可维护性差，难以测试和复用 |
| 13 | 硬编码 userId=1 | 前端 ~8 个文件 | 多用户支持需大面积修改 |
| 14 | `NodeLabel`/`RelType` 非 Enum | graph/schema.py | 无类型安全，无法枚举验证 |

### 6.3 低影响技术债

| # | 债项 | 位置 |
|---|------|------|
| 15 | Alembic revision ID 格式不一致 | alembic/versions/ |
| 16 | `FeedbackType` 在 schemas 和 models 中重复定义 | schemas/feedback.py, models/feedback.py |
| 17 | `ArxivConnector` 使用弃用的 `asyncio.get_event_loop()` | connectors/arxiv.py |
| 18 | `_get_or_create_user` 在两个 API 模块中重复 | api/v1/feedback.py, api/v1/settings.py |
| 19 | `connectors/__init__.py` 未导出 `ArxivConnector` | connectors/__init__.py |
| 20 | `getApiKey()` 在请求中调用两次 | frontend/src/lib/api.ts |

---

## 7. 测试覆盖审计

### 7.1 后端测试概要

| 类型 | 文件数 | ~用例数 | 质量 |
|------|--------|--------|------|
| 单元测试 | 37 | 300+ | ★★★★☆ 优秀 |
| 集成测试 | 8 | 50+ | ★★★★☆ 良好 |

**后端覆盖强度：** 19/19 services 有测试，3/3 connectors 有测试，4/6 graph 模块有测试。Mock 使用合理且一致。

### 7.2 未覆盖的高风险后端模块

| 模块 | 风险等级 | 原因 |
|------|---------|------|
| `services/review_service.py` | 🔴 高 | FSRS 复习卡片服务**完全无测试** |
| `api/v1/content.py` | 🟡 中 | 最常用的 CRUD 端点无测试 |
| `api/v1/dashboard.py` | 🟡 中 | N+1 查询逻辑未验证 |
| `api/v1/pipeline.py` | 🟡 中 | Pipeline 控制端点无测试 |
| `api/v1/kg.py` | 🟡 中 | 包含 Cypher 注入风险的端点无测试 |
| `llm/deepseek.py` | 🟡 中 | 主 LLM 客户端仅通过 mock 间接测试 |
| `llm/ollama.py` | 🟡 中 | 仅间接测试 |

### 7.3 前端测试概要

| 类型 | 文件数 | ~用例数 | 质量 |
|------|--------|--------|------|
| Vitest 单元 | ~15 | ~65 | ★★★☆☆ 中等 |
| Playwright E2E | 3 | 8 | ★★☆☆☆ 极弱 |

**前端关键缺失：**
- `LoginPage` — 认证流程无测试
- `SearchPage`（707 行最复杂页面）— 无测试
- `AuthGuard` — 无测试
- Zustand stores — 无测试
- E2E 测试只验证 DOM 存在性，无真实用户流程

## 8. 安全、可靠性、可维护性评估

### 8.1 安全问题

| # | 问题 | 严重性 | 位置 |
|---|------|--------|------|
| 3 | Bot 无用户白名单 | 🟡 中 | bot/handlers/commands.py |
| 4 | 默认 API Key `alicesecret` | 🟡 中 | config/__init__.py |
| 5 | Cookie 缺少 `Secure` 标记 | 🟡 中 | frontend/src/lib/store.ts |
| 6 | Meilisearch 默认 `masterKey` | 🟡 中 | .env.example |
| 7 | Neo4j 密码硬编码在 docker-compose | 🟢 低 | docker-compose.yml |

### 8.2 可靠性问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | Pipeline retry 后状态可能为 `failed` | 任务重试行为不可预测 |
| 2 | `deliver_push` 统一 commit | 中途失败导致已推的内容不标记 pushed_at |
| 3 | `task_retry_failed` 无最大重试次数 | 永久失败的内容无限重试 |
| 4 | 反馈不幂等 | 用户多次点击创建多条记录 |
| 5 | `_dispatch_skill_execution` 使用未 await 的 `create_task` | 任务可能被 GC 回收 |
| 6 | `get_shared_graph_client` 无并发保护 | 多协程同时调用可能泄漏连接 |

### 8.3 可维护性评价

**优点：**
- 分层架构清晰（API → Service → Storage → Model）
- LLMClient Protocol 抽象设计优秀
- Pydantic 模型覆盖全面
- 测试基础扎实

**问题：**
- 20 个 service 文件之间依赖图复杂，`push.py` 是超级节点（依赖 6 个其他 service）
- 无依赖注入框架，service 实例化散布在调用点
- 前端几乎全部是 `'use client'`，未发挥 Server Components 优势

---

## 9. 可执行建议（按优先级）

### 立即修复（本周）

| # | 行动 | 工作量 | 影响 |
|---|------|--------|------|
| 5 | LoginPage 添加 Suspense boundary | 0.5h | 前端构建 |

### 短期修复（1-2 周）

| # | 行动 | 工作量 | 影响 |
|---|------|--------|------|
| 9 | 统一 Beat Schedule 到单个来源（删除两个死 scheduler 文件） | 2h | 可维护性 |
| 10 | `push.py` 的依赖注入重构（构造函数接收而非每次创建） | 3h | 性能+正确性 |
| 11 | 修复 `task_run_understanding` retry 状态不一致 | 1h | 可靠性 |
| 12 | 统一 URL 规范化到单个函数 | 2h | 一致性 |
| 13 | 添加 `review_service` 单元测试 | 3h | 覆盖率 |
| 14 | OllamaClient 使用持久化 httpx.AsyncClient | 1h | 性能 |

### 中期改进（1-2 月）

| # | 行动 | 工作量 | 影响 |
|---|------|--------|------|
| 15 | 前端迁移到 TanStack Query | 8h | 代码质量+缓存+UX |
| 16 | 建立 CI pipeline（lint + test + type check） | 4h | 质量门禁 |
| 17 | 建立统一的事务管理策略（UnitOfWork 模式或明确规约） | 6h | 一致性 |
| 18 | 清理所有 `importlib` 动态导入（解决循环依赖根因） | 3h | 可维护性 |
| 19 | 补齐缺失的 API 端点测试（content, pipeline, kg, dashboard） | 8h | 覆盖率 |
| 20 | 前端 E2E 测试重写（实际用户流程） | 6h | 质量门禁 |
| 21 | LLMClient Protocol 添加 `close()` / `__aenter__` / `__aexit__` | 2h | 资源管理 |
| 22 | 拆分前端大文件（SearchPage, KnowledgeGraph） | 4h | 可维护性 |
| 23 | Dashboard 查询优化（合并为 GROUP BY 聚合） | 3h | 性能 |
| 24 | 删除所有确认的死代码 | 4h | 代码卫生 |

### 长期架构改进

| # | 行动 |
|---|------|
| 25 | 引入依赖注入框架（如 `dependency-injector`），消除 service 层的手动实例化 |
| 26 | 建立多用户支持（user context 贯穿 API → Service → Task） |
| 27 | 添加可观测性（OpenTelemetry tracing, Prometheus metrics） |
| 28 | 生产部署指南（TLS, 密钥管理, 备份, 监控告警） |

---

## 附录 A：文件级问题速查表

| 文件 | 问题数 | 最高严重性 |
|------|--------|-----------|
| [pipeline/tasks.py](src/alice/pipeline/tasks.py) | 8 | 🔴 P1 |
| [services/push.py](src/alice/services/push.py) | 4 | 🟡 P1 |
| [llm/deepseek.py](src/alice/llm/deepseek.py) | 4 | 🟡 P1 |
| [llm/ollama.py](src/alice/llm/ollama.py) | 5 | 🟡 P1 |
| [worker/celery_app.py](src/alice/worker/celery_app.py) | 2 | 🟡 P1 |
| [api/v1/dashboard.py](src/alice/api/v1/dashboard.py) | 5 | 🟡 P2 |
| [services/kg_updater.py](src/alice/services/kg_updater.py) | 3 | 🟡 P2 |
| [services/matching.py](src/alice/services/matching.py) | 3 | 🟡 P2 |
| [services/storage.py](src/alice/services/storage.py) | 4 | 🟡 P2 |
| [services/graphrag_query.py](src/alice/services/graphrag_query.py) | 4 | 🟡 P2 |
| [graph/repository.py](src/alice/graph/repository.py) | 4 | 🟡 P2 |
| [frontend/src/app/feed/page.tsx](frontend/src/app/feed/page.tsx) | 3 | 🟡 P1 |
| [frontend/src/app/search/page.tsx](frontend/src/app/search/page.tsx) | 4 | 🟡 P2 |
| [frontend/src/components/graph/KnowledgeGraph.tsx](frontend/src/components/graph/KnowledgeGraph.tsx) | 3 | 🟡 P2 |

---

*审计完成。本报告基于对仓库内所有源文件（~120 个 Python 文件、~40 个 TypeScript/TSX 文件、6 个迁移文件、8 个 Jinja2 模板、5 个文档、7 个配置文件）的逐文件分析生成。*
