"""FastAPI application factory."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from chatbot.api.errors import install_error_handlers
from chatbot.api.routes_conversations import router as conversations_router
from chatbot.api.routes_health import router as health_router
from chatbot.config import get_settings
from chatbot.logging import RequestIdMiddleware, configure_logging
from chatbot.persistence.db import dispose_engine, init_engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Initialize and release process-wide resources."""
    settings = get_settings()
    init_engine(settings.database_url)
    try:
        yield
    finally:
        await dispose_engine()


def create_app() -> FastAPI:
    """Build the application. Tests call this directly."""
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Chatbot MVP API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(RequestIdMiddleware)
    install_error_handlers(app)
    app.include_router(health_router, prefix="/api")
    app.include_router(conversations_router, prefix="/api")
    return app


app = create_app()
