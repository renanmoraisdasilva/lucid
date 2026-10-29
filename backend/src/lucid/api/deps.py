"""HTTP dependencies shared by the routes."""

from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lucid.application.registry import GenerationRegistry
from lucid.domain.errors import ConfigurationError
from lucid.domain.provider import ChatProvider
from lucid.persistence.db import get_session, get_session_factory

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_provider(request: Request) -> ChatProvider:
    """The provider built at startup, injected for tests via app.state."""
    provider: object = getattr(request.app.state, "provider", None)
    if not isinstance(provider, ChatProvider):
        raise ConfigurationError("Chat provider is not initialized")
    return provider


def get_system_prompt(request: Request) -> str:
    """The validated system prompt loaded at startup."""
    prompt: object = getattr(request.app.state, "system_prompt", None)
    if not isinstance(prompt, str) or not prompt:
        raise ConfigurationError("System prompt is not initialized")
    return prompt


def get_generation_registry(request: Request) -> GenerationRegistry:
    """The process-wide registry of active generations."""
    registry: object = getattr(request.app.state, "registry", None)
    if not isinstance(registry, GenerationRegistry):
        raise ConfigurationError("Generation registry is not initialized")
    return registry


def get_session_factory_dependency(
    request: Request,
) -> async_sessionmaker[AsyncSession]:
    """Session factory for the streaming path, overridable in tests."""
    factory: object = getattr(request.app.state, "session_factory", None)
    if isinstance(factory, async_sessionmaker):
        return cast("async_sessionmaker[AsyncSession]", factory)
    return get_session_factory()


ProviderDep = Annotated[ChatProvider, Depends(get_provider)]
SystemPromptDep = Annotated[str, Depends(get_system_prompt)]
RegistryDep = Annotated[GenerationRegistry, Depends(get_generation_registry)]
SessionFactoryDep = Annotated[
    async_sessionmaker[AsyncSession], Depends(get_session_factory_dependency)
]
