FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv
WORKDIR /app

COPY pyproject.toml uv.lock README.md alembic.ini ./
RUN uv sync --frozen --no-editable --no-install-project

COPY src/ ./src/
COPY alembic/ ./alembic/
RUN uv sync --frozen --no-editable


FROM python:3.12-slim AS runtime
WORKDIR /app

COPY --from=builder /app /app

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["uvicorn", "alice.main:app", "--host", "0.0.0.0", "--port", "8000"]