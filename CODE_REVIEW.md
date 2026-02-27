Code review findings (2026-02-27)

- KG feedback updates do not create knowledge edges: `KGUpdater` calls `UserKnowledgeGraph.update_mastery`, which only MATCH-es existing `KNOWS` relationships and never ensures/merges them. For new users with no prior graph state, feedback-driven updates are no-ops (src/alice/services/kg_updater.py:105-146, src/alice/graph/user_kg.py:145-155).
- Hybrid search ignores user context: `GraphRAGQueryEngine` accepts `user_id` and even instantiates `UserKnowledgeGraph`, but the ID is never used and `_graph_search` runs a global query. Results are not personalized despite the API contract (src/alice/services/graphrag_query.py:117-222).
- RSS connector blocks the event loop: `RSSConnector.fetch` is `async` but performs blocking `httpx.get` and `trafilatura.fetch_url/extract` calls. When invoked from the async fetch pipeline, a slow feed stalls the entire loop and prevents concurrent source fetches (src/alice/connectors/rss.py:80-176).
- Unsafe defaults for API auth: `Settings.ALICE_API_KEY` ships as the literal `"alicesecret"`, and middleware only compares the header value. Deployments that forget to override the env var leave the API effectively open to anyone who knows the default (src/alice/config/__init__.py:10-47; src/alice/main.py:26-44).

Tests
- uv/pytest unavailable in the environment (`uv run ruff check .` and `uv run pytest` fail: uv missing; `python -m pytest` fails: pytest not installed).
