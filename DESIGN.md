# Alice — AI Secretary 设计文档（实现对齐版）

**Last Updated:** 2026-02-27

> 本文档只描述两类内容：
>
> 1. 当前仓库已经实现并可运行的设计
> 2. 明确标注为 Roadmap 的后续规划
>
> 任何未标注为 Roadmap 的条目，都应能在当前代码中找到对应实现。

## 1. 目标与边界

Alice 是一个个人智能信息管理系统，当前目标是建立稳定的“采集 -> 处理 -> 排序 -> 推送 -> 反馈”闭环，并在此基础上逐步强化个性化推荐与知识图谱能力。

当前阶段不追求覆盖全部内容源，而是优先保证：

- RSS / arXiv 两类连接器稳定运行
- 4-stage pipeline 可恢复、可重试、可观测
- Web + Bot 双端可用
- 数据库、搜索、图谱三套存储能互相协同

## 2. 当前实现架构

### 2.1 服务拓扑

| 服务 | 职责 | 端口 |
| --- | --- | --- |
| `api` | FastAPI API，提供 source/content/pipeline/search/settings/feedback 接口 | 8000 |
| `bot` | aiogram webhook 服务，处理推送交互和 feedback callback | 8081 |
| `worker` | 执行 pipeline Celery 任务 | - |
| `scheduler` | Celery Beat 定时触发 fetch/retry | - |
| `postgres` | 主数据存储（content/source/user/feedback/...） | 5432 |
| `redis` | Celery broker/backend | 6379 |
| `meilisearch` | 全文检索索引 | 7700 |
| `neo4j` | 概念图谱与用户知识图谱 | 7474/7687 |

### 2.2 关键流程

#### API 鉴权

- `/api/*` 默认由 `APIKeyMiddleware` 统一校验 `X-API-Key`
- `/health`、文档路由不走鉴权

#### 内容主链路

1. `POST /api/v1/sources` 创建源
2. 后台触发 `task_fetch_all_sources`
3. 原始内容入库（`pipeline_status=fetched`）
4. `task_run_gatekeeper`
5. `task_run_understanding`
6. `task_run_graph_extraction`
7. `task_run_scoring`
8. `task_run_indexing`
9. `task_push_batch` 推送到 Telegram（可手动触发）

#### 失败与恢复

- 各阶段异常会写入 `pipeline_error`，并设置 `pipeline_status=failed`
- Beat 定时执行 `task_retry_failed`，自动重试非 gatekeeper 永久拒绝项

## 3. 代码模块设计

### 3.1 API 层（`src/alice/api/v1`）

当前路由：

- `content`: 列表、详情、删除、批量删除、图谱补抽取
- `sources`: 增删改查源
- `connectors`: RSS 拉取调试接口
- `pipeline`: process/status/retry/fetch trigger/push trigger/push preview
- `search`: 检索与建议词
- `settings`: 推送偏好读取与更新
- `feedback`: 用户反馈入库

约束：

- 路由层只负责请求校验与编排，不承载核心业务
- 业务逻辑下沉到 `services/*`

### 3.2 Service 层（`src/alice/services`）

主要服务：

- `storage.py`: content CRUD、状态流转、去重 URL 归一化
- `source_service.py`: source CRUD
- `understanding.py`: LLM 结构化理解
- `scoring.py`: 质量评分（基础版 + 7 维评分）
- `ranking.py`: `P_score` 计算与批量更新
- `push.py`: 推送批次查询、卡片渲染、发送落库
- `search.py`: Meilisearch 索引与查询
- `gatekeeper.py`: 内容前置筛选（Ollama 不可用时存在规则回退）

### 3.3 Pipeline 任务层

- `alice.pipeline.tasks`: 当前生效的 pipeline 任务定义
- `alice.worker.tasks`: 仅保留旧任务名兼容 + 拉取入口

设计原则：

- 任务按阶段独立，不使用 Celery chain
- 每阶段显式写库记录状态，保证可追踪与可恢复

### 3.4 LLM 抽象层

- 协议：`alice.llm.protocol.LLMClient`
- Provider：`deepseek`、`ollama`、`mock`
- 统一由 `create_llm_client()` 构建

### 3.5 图谱层（Neo4j）

- `GraphClient`: 连接与查询封装
- `GraphRepository`: 概念节点/关系写入与读取
- `SubgraphExtractor`: 从内容理解结果提取子图并写入 Neo4j
- `UserKnowledgeGraph`: 用户 KNOWS 关系与 mastery 维护

## 4. 数据模型（PostgreSQL）

当前核心表：

- `sources`: 配置的数据源（`rss|arxiv`）
- `content`: 内容主表（pipeline 状态、分数、摘要、推送时间等）
- `users`: 用户与偏好
- `feedback`: 用户对内容的反馈
- `review_cards`: FSRS 复习卡片
- `user_memories`: working/short_term/long_term 记忆项

迁移规范：

- 结构变更必须通过 Alembic
- 严禁直接手工改表

## 5. 存储协同策略

- PostgreSQL: 事务主存、状态机主真相
- Meilisearch: 检索与建议词
- Neo4j: 概念图和用户知识图

同步策略：

- pipeline 完成索引阶段后再进入可推送集合
- 删除内容时采用“先删 DB，再 best-effort 删 Meilisearch”
- 图谱抽取失败不阻塞主 pipeline（记录日志并继续）

## 6. 前端设计现状

前端（Next.js App Router）当前页面：

- `/login` API key 登录
- `/feed` 信息流与反馈操作
- `/content/[id]` 内容详情（含子图可视化组件）
- `/search` 全文检索
- `/settings` source + push 偏好管理

关键约束：

- 前端通过 `X-API-Key` 访问后端
- 中间件基于 cookie 判断登录态
- API base 可通过 `NEXT_PUBLIC_API_URL` 或 `API_URL` 覆盖

## 7. 测试与质量门禁

### 7.1 当前测试分层

- `tests/unit`: 单元测试
- `tests/integration`: 集成测试（真实 DB/图谱依赖按环境变量启用）
- `frontend`:
  - Vitest 组件/逻辑测试
  - Playwright 页面级 E2E

### 7.2 强制质量原则

1. 测试驱动必须覆盖真实数据与真实依赖，不可只停留在 mock 单测。
2. 新模块必须完成系统集成验证，不允许孤立提交。
3. 生产路径不得引入模拟分支替代真实逻辑。
4. 配置必须可用于真实生产运行，禁止伪造参数。
5. 禁止以 TODO 注释替代实现交付。

### 7.3 当前历史技术债（明确记录）

以下是已有代码中的历史兼容做法，不代表目标状态：

- 部分 integration 测试仍使用 patch 隔离网络或 Celery dispatch
- gatekeeper 在 Ollama 不可用时存在规则回退路径
- `alice.worker.tasks` 仍保留 legacy stub 名称兼容

后续演进要求：

- 新增关键功能时，同步补齐“真实依赖链路”验收测试
- 分阶段减少并最终移除生产路径中的兼容性回退

## 8. 新模块接入规范（防止“写完即孤岛”）

新增模块必须同时完成：

1. 模块实现本体
2. API 或任务编排接入点
3. 配置项（`settings` + `.env.example` + README）
4. 存储层迁移（若涉及 schema）
5. 单元测试 + 至少一个真实依赖的集成测试
6. 文档更新（README + DESIGN + AGENTS 至少一处）

## 9. Roadmap（明确标记为规划）

### 9.1 Near-term

- 将 Phase2/3 相关能力（matching、memory、fsrs）从“部分实现”推进到“主链路启用”
- 提升 push 排序中 `R_relevance` 与时间窗调度精度
- 完成 API 鉴权与前端登录相关 E2E 的全链路稳定测试

### 9.2 Mid-term

- 扩展更多 connector（在 RSS/arXiv 稳定前不盲目扩量）
- 完成跨端反馈到 KG 更新的线上闭环监控
- 自动报告与复习计划的生产级调度

### 9.3 Long-term

- 更高质量的探索/利用平衡策略
- 可解释推荐（why this item）可视化增强
- 多语言知识图谱融合与跨域推送策略

## 10. 文档治理规则

- 代码变更涉及接口、配置、运行方式时，必须同步更新本文档。
- 本文档只写“已实现”与“显式规划”两类内容，禁止混写导致误导。
- 若实现与文档冲突，以代码为准，并在同一提交中修正文档。
