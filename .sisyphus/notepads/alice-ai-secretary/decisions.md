# Decisions — alice-ai-secretary

## [2026-02-26] Wave 0.1 Architectural Decisions

### LLM Abstraction
- `LLMClient` is a `@runtime_checkable` Protocol in `src/alice/llm/protocol.py`
- `MockLLMClient` loads from `tests/fixtures/llm_responses/*.json`
- Factory: `create_llm_client(provider: str) -> LLMClient` in `factory.py`
- DeepSeek uses OpenAI SDK with `base_url="https://api.deepseek.com"`, 3 retries, 600s timeout
- Ollama connects to `OLLAMA_HOST` env var (default `host.docker.internal:11434`)

### DB Schema
- 4 tables: users, source, content, feedback
- `PipelineStatus` enum: fetched/gatekept/understood/scored/indexed/failed
- `SourceType` enum: rss/arxiv
- `FeedbackType` enum: valuable_learned/save_for_later/not_valuable/already_known
- All models use `TimestampMixin` (created_at, updated_at)
- Alembic async engine in `env.py`

### Celery Infrastructure
- 6 stub tasks: gatekeeper, understanding, scoring, indexing, fetch, push_batch
- Beat schedule in `celery_app.py` — run every 30 min by default
- Individual tasks only (NO chains)
- Redis with `appendonly yes` for persistence

### Prompt Strategy
- 4 Jinja2 templates: gatekeeper.j2, understanding.j2, quality_score.j2, push_reason.j2
- `PromptManager` in `src/alice/prompts.py` — loads+renders with Jinja2
- All prompts return JSON format; bilingual (Chinese/English) support
