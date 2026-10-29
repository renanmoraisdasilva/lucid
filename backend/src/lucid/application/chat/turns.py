"""Prepare a turn: conversation, user message and generation attempt."""

import uuid
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from lucid.domain.enums import Role
from lucid.persistence.repositories import (
    AttemptRepository,
    ConversationRepository,
    MessageRepository,
)
from lucid.persistence.tables import GenerationAttempt


class ConversationNotFoundError(LookupError):
    """The requested conversation does not exist."""


class MessageNotFoundError(LookupError):
    """The requested message does not exist in that conversation."""


class GenerationInProgressError(RuntimeError):
    """A generation is already running for this conversation."""

    def __init__(self, attempt_id: uuid.UUID) -> None:
        super().__init__("A response is already being generated for this conversation.")
        self.attempt_id = attempt_id


class GenerationAlreadyCompletedError(RuntimeError):
    """Retry requested for a message that already has a completed response."""


@dataclass(frozen=True, slots=True)
class PreparedGeneration:
    """Everything the stream needs, created before the response starts."""

    conversation_id: uuid.UUID
    conversation_title: str
    user_message_id: uuid.UUID
    attempt_id: uuid.UUID
    is_new_conversation: bool


@dataclass(frozen=True, slots=True)
class AttemptRequest:
    """The identifiers needed to open one generation attempt."""

    conversation_id: uuid.UUID
    user_message_id: uuid.UUID
    provider_name: str
    model: str


async def _create_attempt(
    session: AsyncSession,
    attempts: AttemptRepository,
    conversations: ConversationRepository,
    request: AttemptRequest,
) -> GenerationAttempt:
    """Create the attempt and commit the turn in one transaction."""
    try:
        attempt = await attempts.create(
            conversation_id=request.conversation_id,
            user_message_id=request.user_message_id,
            provider=request.provider_name,
            model=request.model,
        )
        await conversations.touch(request.conversation_id)
        await session.commit()
    except IntegrityError as error:
        # The partial unique index rejected a concurrent attempt.
        await session.rollback()
        active = await attempts.get_active_for_conversation(request.conversation_id)
        if active is not None:
            raise GenerationInProgressError(active.id) from error
        raise
    return attempt


async def prepare_message(
    session: AsyncSession,
    *,
    content: str,
    conversation_id: uuid.UUID | None,
    provider_name: str,
    model: str,
) -> PreparedGeneration:
    """Create or continue a conversation and open a generation attempt."""
    conversations = ConversationRepository(session)
    messages = MessageRepository(session)
    attempts = AttemptRepository(session)

    if conversation_id is None:
        conversation = await conversations.create(first_message=content)
        is_new = True
    else:
        conversation = await conversations.get(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(str(conversation_id))
        is_new = False

    active = await attempts.get_active_for_conversation(conversation.id)
    if active is not None:
        raise GenerationInProgressError(active.id)

    user_message = await messages.append(
        conversation_id=conversation.id, role=Role.USER, content=content
    )
    attempt = await _create_attempt(
        session,
        attempts,
        conversations,
        AttemptRequest(conversation.id, user_message.id, provider_name, model),
    )
    return PreparedGeneration(
        conversation_id=conversation.id,
        conversation_title=conversation.title,
        user_message_id=user_message.id,
        attempt_id=attempt.id,
        is_new_conversation=is_new,
    )


async def prepare_retry(
    session: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    provider_name: str,
    model: str,
) -> PreparedGeneration:
    """Open a new attempt for an existing user message. Never duplicates it."""
    conversations = ConversationRepository(session)
    messages = MessageRepository(session)
    attempts = AttemptRepository(session)

    conversation = await conversations.get(conversation_id)
    if conversation is None:
        raise ConversationNotFoundError(str(conversation_id))

    message = await messages.get(message_id)
    if message is None or message.conversation_id != conversation_id:
        raise MessageNotFoundError(str(message_id))
    if message.role != Role.USER.value:
        raise MessageNotFoundError(str(message_id))

    if await attempts.has_completed_for_user_message(message_id):
        raise GenerationAlreadyCompletedError("That message already has a completed response.")

    active = await attempts.get_active_for_conversation(conversation_id)
    if active is not None:
        raise GenerationInProgressError(active.id)

    attempt = await _create_attempt(
        session,
        attempts,
        conversations,
        AttemptRequest(conversation_id, message_id, provider_name, model),
    )
    return PreparedGeneration(
        conversation_id=conversation_id,
        conversation_title=conversation.title,
        user_message_id=message_id,
        attempt_id=attempt.id,
        is_new_conversation=False,
    )
