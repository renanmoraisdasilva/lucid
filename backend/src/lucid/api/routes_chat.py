"""Temporary chat endpoint (replaced by the SSE path in Milestone 4)."""

from fastapi import APIRouter

from lucid.api.deps import ProviderDep, SessionDep, SystemPromptDep
from lucid.api.errors import ApiError
from lucid.api.schemas import ChatRequest, ChatResponse, UsageOut
from lucid.application.chat import ConversationNotFoundError, send_message_once
from lucid.config import get_settings
from lucid.domain.errors import (
    ProviderError,
    ProviderRateLimited,
    ProviderTimeout,
)
from lucid.domain.provider import Usage

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def send_message_endpoint(
    payload: ChatRequest,
    session: SessionDep,
    provider: ProviderDep,
    system_prompt: SystemPromptDep,
) -> ChatResponse:
    """Send one message and return the complete assistant reply.

    Streaming replaces this in Milestone 4; the frontend never consumes it.
    """
    settings = get_settings()
    try:
        outcome = await send_message_once(
            session,
            provider=provider,
            system_prompt=system_prompt,
            model=settings.gemini_model,
            max_output_tokens=settings.gemini_max_output_tokens,
            content=payload.content,
            conversation_id=payload.conversation_id,
        )
    except ConversationNotFoundError as error:
        raise ApiError(
            "conversation_not_found", "That conversation does not exist.", status_code=404
        ) from error
    except ProviderRateLimited as error:
        raise _provider_api_error(error, status_code=429) from error
    except ProviderTimeout as error:
        raise _provider_api_error(error, status_code=504) from error
    except ProviderError as error:
        raise _provider_api_error(error, status_code=502) from error

    return ChatResponse(
        conversation_id=outcome.conversation.id,
        user_message_id=outcome.user_message.id,
        attempt_id=outcome.attempt.id,
        assistant_message_id=(
            outcome.assistant_message.id if outcome.assistant_message is not None else None
        ),
        attempt_status=outcome.attempt_status,
        content=outcome.content,
        usage=_usage_out(outcome.usage),
    )


def _provider_api_error(error: ProviderError, *, status_code: int) -> ApiError:
    return ApiError(error.code, str(error), status_code=status_code)


def _usage_out(usage: Usage | None) -> UsageOut | None:
    if usage is None:
        return None
    return UsageOut(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        thought_tokens=usage.thought_tokens,
        total_tokens=usage.total_tokens,
    )
