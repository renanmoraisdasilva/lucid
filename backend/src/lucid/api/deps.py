"""HTTP dependencies shared by the routes."""

from dataclasses import dataclass
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lucid.application.cooldown import RateLimitCooldown
from lucid.application.models import ModelCatalog
from lucid.application.registry import GenerationRegistry
from lucid.domain.errors import ConfigurationError
from lucid.persistence.db import get_session, get_session_factory
from lucid.providers.factory import ProviderRegistry

SessionDep = Annotated[AsyncSession, Depends(get_session)]


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


def get_cooldown(request: Request) -> RateLimitCooldown:
    """The shared provider rate-limit cooldown."""
    cooldown: object = getattr(request.app.state, "cooldown", None)
    if not isinstance(cooldown, RateLimitCooldown):
        raise ConfigurationError("Rate limit cooldown is not initialized")
    return cooldown


def get_catalog(request: Request) -> ModelCatalog:
    """The model catalogue built at startup."""
    catalog: object = getattr(request.app.state, "catalog", None)
    if not isinstance(catalog, ModelCatalog):
        raise ConfigurationError("Model catalogue is not initialized")
    return catalog


def get_providers(request: Request) -> ProviderRegistry:
    """The lazily built provider registry."""
    providers: object = getattr(request.app.state, "providers", None)
    if not isinstance(providers, ProviderRegistry):
        raise ConfigurationError("Provider registry is not initialized")
    return providers


def get_session_factory_dependency(
    request: Request,
) -> async_sessionmaker[AsyncSession]:
    """Session factory for the streaming path, overridable in tests."""
    factory: object = getattr(request.app.state, "session_factory", None)
    if isinstance(factory, async_sessionmaker):
        return cast("async_sessionmaker[AsyncSession]", factory)
    return get_session_factory()


SystemPromptDep = Annotated[str, Depends(get_system_prompt)]
RegistryDep = Annotated[GenerationRegistry, Depends(get_generation_registry)]
CooldownDep = Annotated[RateLimitCooldown, Depends(get_cooldown)]
CatalogDep = Annotated[ModelCatalog, Depends(get_catalog)]
ProvidersDep = Annotated[ProviderRegistry, Depends(get_providers)]
SessionFactoryDep = Annotated[
    async_sessionmaker[AsyncSession], Depends(get_session_factory_dependency)
]


@dataclass(frozen=True, slots=True)
class StreamDeps:
    """Everything the chat stream needs, resolved once per request.

    The provider and the model are per request (they come from the catalogue and
    the request body), so the route resolves them from `catalog`/`providers`.
    """

    system_prompt: str
    session_factory: async_sessionmaker[AsyncSession]
    registry: GenerationRegistry
    cooldown: RateLimitCooldown
    catalog: ModelCatalog
    providers: ProviderRegistry


def get_stream_deps(request: Request) -> StreamDeps:
    """Bundle the streaming dependencies so routes stay small."""
    return StreamDeps(
        system_prompt=get_system_prompt(request),
        session_factory=get_session_factory_dependency(request),
        registry=get_generation_registry(request),
        cooldown=get_cooldown(request),
        catalog=get_catalog(request),
        providers=get_providers(request),
    )


StreamDepsDep = Annotated[StreamDeps, Depends(get_stream_deps)]
