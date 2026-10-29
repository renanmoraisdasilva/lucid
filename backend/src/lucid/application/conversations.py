"""Read models and queries for conversation views."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from lucid.application.cursor import Cursor, decode_cursor, encode_cursor
from lucid.domain.enums import AttemptStatus, Role
from lucid.persistence.repositories import (
    AttemptRepository,
    ConversationRepository,
    MessageRepository,
)
from lucid.persistence.tables import Conversation, GenerationAttempt, Message

# Failures the user cannot fix by retrying. Anything else terminal is retryable.
NON_RETRYABLE_ERROR_CODES = frozenset(
    {
        "validation_error",
        "context_too_large",
        "provider_invalid_request",
        "provider_safety_blocked",
    }
)


@dataclass(frozen=True, slots=True)
class MessageView:
    """A message plus the attempt metadata the UI needs to render it."""

    message: Message
    attempt: GenerationAttempt | None
    retryable: bool


@dataclass(frozen=True, slots=True)
class ConversationView:
    """A conversation with its transcript and active generation, if any."""

    conversation: Conversation
    messages: Sequence[MessageView]
    active_attempt_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class ConversationListItem:
    """A conversation row plus its active generation, for the sidebar."""

    conversation: Conversation
    active_attempt_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class ConversationPageView:
    """One page of conversations and the cursor for the next page."""

    items: Sequence[ConversationListItem]
    next_cursor: str | None
    has_more: bool


async def list_conversations(
    session: AsyncSession,
    *,
    limit: int,
    cursor_token: str | None,
) -> ConversationPageView:
    """Return one page of conversations, most recently updated first."""
    cursor: Cursor | None = decode_cursor(cursor_token) if cursor_token is not None else None

    page = await ConversationRepository(session).list_page(limit=limit, cursor=cursor)
    if not page.items:
        return ConversationPageView(items=[], next_cursor=None, has_more=False)

    conversation_ids = [conversation.id for conversation in page.items]
    active_attempts = await AttemptRepository(session).list_active_for_conversations(
        conversation_ids
    )
    active_by_conversation = {attempt.conversation_id: attempt.id for attempt in active_attempts}

    items = [
        ConversationListItem(
            conversation=conversation,
            active_attempt_id=active_by_conversation.get(conversation.id),
        )
        for conversation in page.items
    ]

    next_cursor = None
    if page.has_more:
        last = page.items[-1]
        next_cursor = encode_cursor(Cursor(updated_at=last.updated_at, id=last.id))

    return ConversationPageView(items=items, next_cursor=next_cursor, has_more=page.has_more)


async def read_conversation(
    session: AsyncSession,
    conversation_id: uuid.UUID,
) -> ConversationView | None:
    """Load a conversation with its messages and attempt summaries."""
    conversation = await ConversationRepository(session).get(conversation_id)
    if conversation is None:
        return None

    messages = await MessageRepository(session).list_for_conversation(conversation_id)
    attempts = await AttemptRepository(session).list_for_conversation(conversation_id)

    latest_by_user_message: dict[uuid.UUID, GenerationAttempt] = {}
    attempt_by_assistant_message: dict[uuid.UUID, GenerationAttempt] = {}
    active_attempt_id: uuid.UUID | None = None

    for attempt in attempts:
        current = latest_by_user_message.get(attempt.user_message_id)
        if current is None or attempt.attempt_no > current.attempt_no:
            latest_by_user_message[attempt.user_message_id] = attempt
        if attempt.assistant_message_id is not None:
            attempt_by_assistant_message[attempt.assistant_message_id] = attempt
        if attempt.status == AttemptStatus.IN_PROGRESS.value:
            active_attempt_id = attempt.id

    views: list[MessageView] = []
    for message in messages:
        if message.role == Role.USER.value:
            attempt = latest_by_user_message.get(message.id)
            views.append(
                MessageView(message=message, attempt=attempt, retryable=_is_retryable(attempt))
            )
        else:
            attempt = attempt_by_assistant_message.get(message.id)
            views.append(MessageView(message=message, attempt=attempt, retryable=False))

    return ConversationView(
        conversation=conversation,
        messages=views,
        active_attempt_id=active_attempt_id,
    )


async def delete_conversation(session: AsyncSession, conversation_id: uuid.UUID) -> bool:
    """Permanently delete a conversation; messages and attempts cascade."""
    deleted = await ConversationRepository(session).delete(conversation_id)
    if deleted:
        await session.commit()
    return deleted


def _is_retryable(attempt: GenerationAttempt | None) -> bool:
    """Retry is offered when the latest attempt ended without a usable response."""
    if attempt is None:
        return False
    if attempt.status in (AttemptStatus.COMPLETED.value, AttemptStatus.IN_PROGRESS.value):
        return False
    return attempt.error_code not in NON_RETRYABLE_ERROR_CODES
