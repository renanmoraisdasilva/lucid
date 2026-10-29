"""Streaming chat endpoints: send, retry, stop.

The response is SSE. Errors detected before the stream starts (404, 409, 422)
use the normal JSON error envelope; anything after `meta` is an `error` event.
"""

import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lucid.api.deps import (
    ProviderDep,
    RegistryDep,
    SessionDep,
    SessionFactoryDep,
    SystemPromptDep,
)
from lucid.api.errors import ApiError
from lucid.api.schemas import ChatRequest, StopGenerationResponse
from lucid.api.sse import SSE_HEADERS, SSE_MEDIA_TYPE, encode_event
from lucid.application.chat_service import (
    ConversationNotFoundError,
    GenerationAlreadyCompletedError,
    GenerationInProgressError,
    MessageNotFoundError,
    PreparedGeneration,
    prepare_message,
    prepare_retry,
    stream_generation,
)
from lucid.application.context import ContextBudget
from lucid.application.registry import GenerationRegistry
from lucid.application.retry import RetryPolicy
from lucid.config import Settings, get_settings
from lucid.domain.enums import AttemptStatus
from lucid.domain.provider import ChatProvider
from lucid.persistence.repositories import AttemptRepository

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def send_message_endpoint(
    payload: ChatRequest,
    session: SessionDep,
    provider: ProviderDep,
    system_prompt: SystemPromptDep,
    session_factory: SessionFactoryDep,
    registry: RegistryDep,
) -> StreamingResponse:
    """Send a message and stream the reply. Creates the conversation if needed."""
    settings = get_settings()
    try:
        prepared = await prepare_message(
            session,
            content=payload.content,
            conversation_id=payload.conversation_id,
            provider_name=provider.name,
            model=settings.gemini_model,
        )
    except ConversationNotFoundError as error:
        raise _conversation_not_found() from error
    except GenerationInProgressError as error:
        raise _generation_in_progress(error) from error

    return _stream_response(
        prepared,
        provider=provider,
        system_prompt=system_prompt,
        session_factory=session_factory,
        registry=registry,
    )


@router.post("/conversations/{conversation_id}/messages/{message_id}/retry")
async def retry_message_endpoint(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    session: SessionDep,
    provider: ProviderDep,
    system_prompt: SystemPromptDep,
    session_factory: SessionFactoryDep,
    registry: RegistryDep,
) -> StreamingResponse:
    """Retry generation for an existing user message."""
    settings = get_settings()
    try:
        prepared = await prepare_retry(
            session,
            conversation_id=conversation_id,
            message_id=message_id,
            provider_name=provider.name,
            model=settings.gemini_model,
        )
    except ConversationNotFoundError as error:
        raise _conversation_not_found() from error
    except MessageNotFoundError as error:
        raise ApiError(
            "message_not_found",
            "That message does not exist in this conversation.",
            status_code=404,
        ) from error
    except GenerationAlreadyCompletedError as error:
        raise ApiError(
            "generation_already_completed",
            "That message already has a completed response.",
            status_code=409,
        ) from error
    except GenerationInProgressError as error:
        raise _generation_in_progress(error) from error

    return _stream_response(
        prepared,
        provider=provider,
        system_prompt=system_prompt,
        session_factory=session_factory,
        registry=registry,
    )


@router.post(
    "/conversations/{conversation_id}/generations/{attempt_id}/stop",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=StopGenerationResponse,
)
async def stop_generation_endpoint(
    conversation_id: uuid.UUID,
    attempt_id: uuid.UUID,
    session: SessionDep,
    registry: RegistryDep,
) -> StopGenerationResponse:
    """Ask the active generation to stop. Idempotent for terminal attempts."""
    attempts = AttemptRepository(session)
    attempt = await attempts.get(attempt_id)
    if attempt is None or attempt.conversation_id != conversation_id:
        raise ApiError("attempt_not_found", "That generation does not exist.", status_code=404)

    if attempt.status != AttemptStatus.IN_PROGRESS.value:
        return StopGenerationResponse(
            attempt_id=attempt_id,
            status=AttemptStatus(attempt.status),
            stop_requested=False,
        )

    tracked = await registry.request_stop(attempt_id)
    if not tracked:
        # No task in this process (for example after a restart): close it here.
        await attempts.finalize(
            attempt_id,
            status=AttemptStatus.INTERRUPTED,
            error_code="cancelled_untracked",
        )
        await session.commit()
        return StopGenerationResponse(
            attempt_id=attempt_id,
            status=AttemptStatus.INTERRUPTED,
            stop_requested=True,
        )

    return StopGenerationResponse(
        attempt_id=attempt_id,
        status=AttemptStatus.IN_PROGRESS,
        stop_requested=True,
    )


def _stream_response(
    prepared: PreparedGeneration,
    *,
    provider: ChatProvider,
    system_prompt: str,
    session_factory: async_sessionmaker[AsyncSession],
    registry: GenerationRegistry,
) -> StreamingResponse:
    settings = get_settings()
    events = stream_generation(
        prepared,
        session_factory=session_factory,
        provider=provider,
        system_prompt=system_prompt,
        model=settings.gemini_model,
        max_output_tokens=settings.gemini_max_output_tokens,
        registry=registry,
        context_budget=_context_budget(settings),
        retry_policy=_retry_policy(settings),
    )

    async def frames() -> AsyncIterator[str]:
        async for event, data in events:
            yield encode_event(event, data)

    return StreamingResponse(frames(), media_type=SSE_MEDIA_TYPE, headers=SSE_HEADERS)


def _conversation_not_found() -> ApiError:
    return ApiError("conversation_not_found", "That conversation does not exist.", status_code=404)


def _generation_in_progress(error: GenerationInProgressError) -> ApiError:
    return ApiError(
        "generation_in_progress",
        str(error),
        status_code=409,
        details={"attempt_id": str(error.attempt_id)},
    )


def _context_budget(settings: Settings) -> ContextBudget:
    return ContextBudget(
        max_input_tokens=settings.context_max_input_tokens,
        reserved_output_tokens=settings.context_reserved_output_tokens,
        safety_margin_tokens=settings.context_safety_margin_tokens,
        max_messages=settings.context_max_messages,
    )


def _retry_policy(settings: Settings) -> RetryPolicy:
    return RetryPolicy(
        max_retries=settings.generation_max_retries,
        base_delay_ms=settings.retry_base_delay_ms,
        max_delay_ms=settings.retry_max_delay_ms,
        jitter=settings.retry_jitter,
    )
