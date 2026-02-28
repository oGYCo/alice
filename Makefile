.PHONY: up down test test-phase2 lint format migrate logs shell clean help

help:
	@echo "Alice — AI Secretary | Development Commands"
	@echo ""
	@echo "Usage:"
	@echo "  make up              Start all Docker services"
	@echo "  make down            Stop all Docker services"
	@echo "  make test            Run pytest on tests/ directory"
	@echo "  make test-phase2     Run phase2 integration test with real env vars"
	@echo "  make lint            Run ruff linter"
	@echo "  make format          Format code with ruff"
	@echo "  make migrate         Run Alembic migrations"
	@echo "  make logs            Watch Docker service logs"
	@echo "  make shell           Start Python REPL"
	@echo "  make clean           Remove .pyc, __pycache__, .pytest_cache"
	@echo ""

up:
	docker compose up -d
	@echo "✓ Alice services starting... (api:8000, bot:8081)"

down:
	docker compose down

test:
	uv run pytest tests/ -v

test-phase2:
	TEST_DATABASE_URL="postgresql+asyncpg://alice:alice@localhost:5432/alice_test" \
	NEO4J_TEST_URI="bolt://localhost:7687" \
	NEO4J_TEST_USER="neo4j" \
	NEO4J_TEST_PASS="alice_neo4j" \
	PHASE2_LLM_PROVIDER="ollama" \
	uv run pytest tests/integration/test_phase2_integration.py -m integration -v

lint:
	uv run ruff check .

format:
	uv run ruff format .

migrate:
	uv run alembic upgrade head

logs:
	docker compose logs -f

shell:
	uv run python

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Cleaned up Python cache files"
