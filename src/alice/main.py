"""FastAPI application factory and main entry point."""

import importlib
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request  # type: ignore[import-not-found]
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from alice.config import settings
from alice.logging import setup_logging
from alice.services.search import SearchService

_connectors_module = importlib.import_module("alice.api.v1.connectors")
_content_module = importlib.import_module("alice.api.v1.content")
_sources_module = importlib.import_module("alice.api.v1.sources")
_pipeline_module = importlib.import_module("alice.api.v1.pipeline")
_settings_module = importlib.import_module("alice.api.v1.settings")
_search_module = importlib.import_module("alice.api.v1.search")
_feedback_module = importlib.import_module("alice.api.v1.feedback")
_dashboard_module = importlib.import_module("alice.api.v1.dashboard")
_kg_module = importlib.import_module("alice.api.v1.kg")

connectors_router = _connectors_module.router
content_router = _content_module.router
sources_router = _sources_module.router
pipeline_router = _pipeline_module.router
settings_router = _settings_module.router
search_router = _search_module.router
feedback_router = _feedback_module.router
dashboard_router = _dashboard_module.router
kg_router = _kg_module.router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: configure external services before first request."""
    # Ensure Meilisearch index exists with correct attribute config.
    # ensure_index is idempotent — safe to call on every startup.
    try:
        search = SearchService(
            url=settings.MEILISEARCH_URL,
            api_key=settings.MEILISEARCH_API_KEY,
        )
        search.ensure_index()
    except Exception:
        # Meilisearch may not be ready yet; startup should not fail.
        import structlog
        structlog.get_logger(__name__).warning("meilisearch_ensure_index_failed_on_startup")
    yield
    # (shutdown hooks can go here in the future)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Require X-API-Key header on all /api/* routes."""

    async def dispatch(self, request: Request, call_next):
        # Skip auth for health check and docs
        skip = ("/health", "/docs", "/openapi.json", "/redoc")
        if not request.url.path.startswith("/api/") or request.url.path in skip:
            return await call_next(request)
        key = request.headers.get("X-API-Key", "")
        if key != settings.ALICE_API_KEY:
            return JSONResponse(status_code=401, content={"detail": "Invalid API key"})
        return await call_next(request)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    setup_logging()

    app = FastAPI(
        title="Alice — AI Secretary",
        description="Personal intelligent information manager",
        version="0.1.0",
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    app.add_middleware(APIKeyMiddleware)

    app.include_router(content_router, prefix="/api/v1")
    app.include_router(sources_router, prefix="/api/v1")
    app.include_router(connectors_router, prefix="/api/v1")
    app.include_router(pipeline_router, prefix="/api/v1")
    app.include_router(settings_router, prefix="/api/v1")
    app.include_router(search_router, prefix="/api/v1")
    app.include_router(feedback_router, prefix="/api/v1")
    app.include_router(dashboard_router, prefix="/api/v1")
    app.include_router(kg_router, prefix="/api/v1")

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "ok", "version": "0.1.0"}

    return app


# Create app instance for uvicorn
app = create_app()
