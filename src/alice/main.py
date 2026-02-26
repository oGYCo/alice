"""FastAPI application factory and main entry point."""

from fastapi import FastAPI  # type: ignore[import-not-found]

from alice.config import settings
from alice.logging import setup_logging

from .api.v1.connectors import router as connectors_router
from .api.v1.content import router as content_router
from .api.v1.sources import router as sources_router


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

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "ok", "version": "0.1.0"}

    return app


# Create app instance for uvicorn
app = create_app()
