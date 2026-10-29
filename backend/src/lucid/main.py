"""FastAPI application factory."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from lucid.api.errors import install_error_handlers
from lucid.api.routes_chat import router as chat_router
from lucid.api.routes_conversations import router as conversations_router
from lucid.api.routes_health import router as health_router
from lucid.application.prompts import load_system_prompt
from lucid.application.registry import GenerationRegistry
from lucid.config import get_settings
from lucid.logging import RequestIdMiddleware, configure_logging
from lucid.persistence.db import (
    dispose_engine,
    get_session_factory,
    init_engine,
)
from lucid.persistence.reconciliation import reconcile_stale_attempts
from lucid.providers.factory import build_provider

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Initialize and release process-wide resources."""
    settings = get_settings()
    init_engine(settings.database_url)
    app.state.provider = build_provider(settings)
    app.state.system_prompt = load_system_prompt(settings.system_prompt_path)
    app.state.session_factory = get_session_factory()
    app.state.registry = GenerationRegistry()

    if settings.reconcile_on_startup:
        await reconcile_stale_attempts(app.state.session_factory)

    logger.info(
        "startup complete",
        extra={
            "ctx_provider": settings.provider,
            "ctx_model": settings.gemini_model,
            "ctx_context_tokens": settings.context_max_input_tokens,
        },
    )
    try:
        yield
    finally:
        await app.state.registry.cancel_all()
        await dispose_engine()


def create_app() -> FastAPI:
    """Build the application. Tests call this directly."""
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Lucid API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(RequestIdMiddleware)
    install_error_handlers(app)
    app.include_router(health_router, prefix="/api")
    app.include_router(conversations_router, prefix="/api")
    app.include_router(chat_router, prefix="/api")
    return app


app = create_app()
