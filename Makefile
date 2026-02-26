.PHONY: up down test lint format migrate logs shell clean help

help:
	@echo "Alice — AI Secretary | Development Commands"
	@echo ""
	@echo "Usage:"
	@echo "  make up              Start all Docker services"
	@echo "  make down            Stop all Docker services"
	@echo "  make test            Run pytest on tests/ directory"
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
