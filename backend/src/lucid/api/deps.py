"""HTTP dependencies shared by the routes."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from lucid.domain.errors import ConfigurationError
from lucid.domain.provider import ChatProvider
from lucid.persistence.db import get_session

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


ProviderDep = Annotated[ChatProvider, Depends(get_provider)]
SystemPromptDep = Annotated[str, Depends(get_system_prompt)]
