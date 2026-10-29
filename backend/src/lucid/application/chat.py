"""Temporary non-streaming chat orchestration (Milestone 3).

This is the smallest path that proves the provider boundary works end to end:
persist the user message, run one generation, persist the outcome. Milestone 4
replaces it with the SSE streaming path.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from lucid.domain.enums import AttemptStatus, Role
from lucid.domain.errors import ProviderError
from lucid.domain.provider import (
    ChatProvider,
    GenerationRequest,
    ProviderMessage,
    TextDelta,
    Usage,
)
from lucid.persistence.repositories import (
    AttemptRepository,
    ConversationRepository,
    MessageRepository,
)
from lucid.persistence.tables import Conversation, GenerationAttempt, Message


class ConversationNotFoundError(LookupError):
    """The requested conversation does not exist."""


@dataclass(frozen=True, slots=True)
class ChatOutcome:
    """Result of one non-streaming turn."""

    conversation: Conversation
    user_message: Message
    attempt: GenerationAttempt
    assistant_message: Message | None
    content: str
    usage: Usage | None
    attempt_status: AttemptStatus


async def send_message_once(
    session: AsyncSession,
    *,
    provider: ChatProvider,
    system_prompt: str,
    model: str,
    max_output_tokens: int,
    content: str,
    conversation_id: uuid.UUID | None = None,
) -> ChatOutcome:
    """Persist the user message, generate a reply, and persist the outcome.

    The user message and attempt are committed before the provider call so a
    failed generation still leaves a retryable record.
    """
    conversations = ConversationRepository(session)
    messages = MessageRepository(session)
    attempts = AttemptRepository(session)

    if conversation_id is None:
        conversation = await conversations.create(first_message=content)
    else:
        conversation = await conversations.get(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(str(conversation_id))

    user_message = await messages.append(
        conversation_id=conversation.id, role=Role.USER, content=content
    )
    attempt = await attempts.create(
        conversation_id=conversation.id,
        user_message_id=user_message.id,
        provider=provider.name,
        model=model,
    )
    await conversations.touch(conversation.id)
    await session.commit()

    history = await messages.list_for_conversation(conversation.id)
    request = GenerationRequest(
        model=model,
        system_prompt=system_prompt,
        messages=[
            ProviderMessage(role=Role(message.role), content=message.content) for message in history
        ],
        max_output_tokens=max_output_tokens,
        request_id=str(attempt.id),
    )

    chunks: list[str] = []
    usage: Usage | None = None
    try:
        async for event in provider.stream(request):
            if isinstance(event, TextDelta):
                chunks.append(event.text)
            else:
                usage = event.usage
    except ProviderError as error:
        await attempts.finalize(
            attempt.id,
            status=AttemptStatus.FAILED,
            error_code=error.code,
            error_message=str(error),
        )
        await session.commit()
        raise

    text = "".join(chunks)
    assistant_message: Message | None = None
    if text:
        assistant_message = await messages.append(
            conversation_id=conversation.id, role=Role.ASSISTANT, content=text
        )
        await conversations.touch(conversation.id)

    await attempts.finalize(
        attempt.id,
        status=AttemptStatus.COMPLETED,
        assistant_message_id=assistant_message.id if assistant_message is not None else None,
        usage=dict(usage.raw) if usage is not None and usage.raw is not None else None,
        input_tokens=usage.input_tokens if usage is not None else None,
        output_tokens=usage.output_tokens if usage is not None else None,
        thought_tokens=usage.thought_tokens if usage is not None else None,
        total_tokens=usage.total_tokens if usage is not None else None,
    )
    await session.commit()

    return ChatOutcome(
        conversation=conversation,
        user_message=user_message,
        attempt=attempt,
        assistant_message=assistant_message,
        content=text,
        usage=usage,
        attempt_status=AttemptStatus.COMPLETED,
    )
