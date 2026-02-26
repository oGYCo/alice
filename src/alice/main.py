"""FastAPI application factory and main entry point."""

import importlib

from fastapi import FastAPI  # type: ignore[import-not-found]

from alice.config import settings
from alice.logging import setup_logging

_connectors_module = importlib.import_module("alice.api.v1.connectors")
_content_module = importlib.import_module("alice.api.v1.content")
_sources_module = importlib.import_module("alice.api.v1.sources")
_pipeline_module = importlib.import_module("alice.api.v1.pipeline")

connectors_router = _connectors_module.router
content_router = _content_module.router
sources_router = _sources_module.router
pipeline_router = _pipeline_module.router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    setup_logging()

    app = FastAPI(
        title="Alice — AI Secretary",
        description="Personal intelligent information manager",
        version="0.1.0",
        debug=settings.DEBUG,
    )

    app.include_router(content_router, prefix="/api/v1")
    app.include_router(sources_router, prefix="/api/v1")
    app.include_router(connectors_router, prefix="/api/v1")
    app.include_router(pipeline_router, prefix="/api/v1")

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "ok", "version": "0.1.0"}

    return app


# Create app instance for uvicorn
app = create_app()
