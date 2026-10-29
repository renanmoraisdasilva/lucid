"""Repository behaviour: sequence allocation, ordering, and keyset pagination."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lucid.application.conversations import list_conversations, read_conversation
from lucid.application.cursor import Cursor
from lucid.domain.enums import AttemptStatus, Role
from lucid.persistence.repositories import (
    AttemptRepository,
    ConversationRepository,
    MessageRepository,
)
from lucid.persistence.tables import Conversation, Message


async def _create_conversations(session: AsyncSession, count: int) -> list[Conversation]:
    created: list[Conversation] = []
    for index in range(count):
        conversation = await ConversationRepository(session).create(
            first_message=f"conversation number {index}"
        )
        await session.commit()
        created.append(conversation)
    return created


async def test_append_allocates_dense_sequence_numbers(session: AsyncSession) -> None:
    conversation = await ConversationRepository(session).create(first_message="hi")
    repository = MessageRepository(session)

    first = await repository.append(conversation_id=conversation.id, role=Role.USER, content="hi")
    second = await repository.append(
        conversation_id=conversation.id, role=Role.ASSISTANT, content="hello"
    )
    third = await repository.append(
        conversation_id=conversation.id, role=Role.USER, content="again"
    )

    assert [first.seq, second.seq, third.seq] == [1, 2, 3]

    messages = await repository.list_for_conversation(conversation.id)
    assert [message.seq for message in messages] == [1, 2, 3]
    assert [message.role for message in messages] == ["user", "assistant", "user"]


async def test_sequence_allocation_is_per_conversation(session: AsyncSession) -> None:
    first = await ConversationRepository(session).create(first_message="one")
    second = await ConversationRepository(session).create(first_message="two")
    repository = MessageRepository(session)

    first_message = await repository.append(conversation_id=first.id, role=Role.USER, content="one")
    second_message = await repository.append(
        conversation_id=second.id, role=Role.USER, content="two"
    )

    assert first_message.seq == 1
    assert second_message.seq == 1


async def test_title_is_derived_from_the_first_message(session: AsyncSession) -> None:
    conversation = await ConversationRepository(session).create(
        first_message="  Explain   the universe\nbriefly "
    )

    assert conversation.title == "Explain the universe briefly"


async def test_created_at_and_updated_at_are_timezone_aware(session: AsyncSession) -> None:
    conversation = await ConversationRepository(session).create(first_message="tz check")
    await session.commit()

    assert conversation.created_at.tzinfo is not None
    assert conversation.updated_at.tzinfo is not None


async def test_list_page_returns_newest_first(session: AsyncSession) -> None:
    created = await _create_conversations(session, 3)

    page = await ConversationRepository(session).list_page(limit=10)

    assert [conversation.id for conversation in page.items] == [
        conversation.id for conversation in reversed(created)
    ]
    assert page.has_more is False


async def test_list_page_paginates_without_duplicates_or_gaps(
    session: AsyncSession,
) -> None:
    created = await _create_conversations(session, 5)
    repository = ConversationRepository(session)

    seen: list[uuid.UUID] = []
    cursor: Cursor | None = None
    pages = 0

    while True:
        page = await repository.list_page(limit=2, cursor=cursor)
        pages += 1
        seen.extend(conversation.id for conversation in page.items)
        if not page.has_more:
            break
        last = page.items[-1]
        cursor = Cursor(updated_at=last.updated_at, id=last.id)

    assert pages == 3
    assert len(seen) == 5
    assert len(set(seen)) == 5
    assert set(seen) == {conversation.id for conversation in created}


async def test_pagination_is_stable_when_new_conversations_arrive(
    session: AsyncSession,
) -> None:
    await _create_conversations(session, 4)
    repository = ConversationRepository(session)

    first_page = await repository.list_page(limit=2)
    last = first_page.items[-1]
    cursor = Cursor(updated_at=last.updated_at, id=last.id)

    inserted = await ConversationRepository(session).create(first_message="brand new")
    await session.commit()

    second_page = await repository.list_page(limit=2, cursor=cursor)
    returned_ids = {conversation.id for conversation in second_page.items}

    assert inserted.id not in returned_ids
    assert returned_ids.isdisjoint({conversation.id for conversation in first_page.items})
    assert len(returned_ids) == 2


async def test_touch_moves_a_conversation_to_the_top(session: AsyncSession) -> None:
    created = await _create_conversations(session, 3)
    oldest = created[0]
    repository = ConversationRepository(session)

    before = await repository.get(oldest.id)
    assert before is not None
    previous_updated_at = before.updated_at

    await repository.touch(oldest.id)
    await session.commit()

    page = await repository.list_page(limit=10)
    assert page.items[0].id == oldest.id

    refreshed = await repository.get(oldest.id)
    assert refreshed is not None
    assert refreshed.updated_at >= previous_updated_at


async def test_list_page_reports_has_more(session: AsyncSession) -> None:
    await _create_conversations(session, 3)

    page = await ConversationRepository(session).list_page(limit=2)

    assert len(page.items) == 2
    assert page.has_more is True


async def test_list_page_on_empty_table(session: AsyncSession) -> None:
    page = await ConversationRepository(session).list_page(limit=10)

    assert page.items == []
    assert page.has_more is False


async def test_application_list_layer_exposes_cursor_and_active_attempt(
    session: AsyncSession,
) -> None:
    conversation = await ConversationRepository(session).create(first_message="with attempt")
    user_message = await MessageRepository(session).append(
        conversation_id=conversation.id, role=Role.USER, content="with attempt"
    )
    attempt = await AttemptRepository(session).create(
        conversation_id=conversation.id,
        user_message_id=user_message.id,
        provider="fake",
        model="fake-model",
    )
    await session.commit()

    page = await list_conversations(session, limit=10, cursor_token=None)

    assert page.has_more is False
    assert page.next_cursor is None
    assert page.items[0].active_attempt_id == attempt.id


async def test_read_conversation_marks_retryable_failed_attempts(
    session: AsyncSession,
) -> None:
    conversation = await ConversationRepository(session).create(first_message="will fail")
    user_message = await MessageRepository(session).append(
        conversation_id=conversation.id, role=Role.USER, content="will fail"
    )
    attempt = await AttemptRepository(session).create(
        conversation_id=conversation.id,
        user_message_id=user_message.id,
        provider="fake",
        model="fake-model",
    )
    await AttemptRepository(session).finalize(
        attempt.id,
        status=AttemptStatus.FAILED,
        error_code="provider_rate_limited",
        error_message="The model is rate limited.",
    )
    await session.commit()

    view = await read_conversation(session, conversation.id)

    assert view is not None
    assert len(view.messages) == 1
    message_view = view.messages[0]
    assert message_view.retryable is True
    assert message_view.attempt is not None
    assert message_view.attempt.status == AttemptStatus.FAILED.value


async def test_read_conversation_does_not_offer_retry_after_success(
    session: AsyncSession,
) -> None:
    conversation = await ConversationRepository(session).create(first_message="succeeds")
    user_message = await MessageRepository(session).append(
        conversation_id=conversation.id, role=Role.USER, content="succeeds"
    )
    attempt = await AttemptRepository(session).create(
        conversation_id=conversation.id,
        user_message_id=user_message.id,
        provider="fake",
        model="fake-model",
    )
    assistant_message = await MessageRepository(session).append(
        conversation_id=conversation.id, role=Role.ASSISTANT, content="done"
    )
    await AttemptRepository(session).finalize(
        attempt.id,
        status=AttemptStatus.COMPLETED,
        assistant_message_id=assistant_message.id,
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
    )
    await session.commit()

    view = await read_conversation(session, conversation.id)

    assert view is not None
    assert view.active_attempt_id is None
    user_view, assistant_view = view.messages
    assert user_view.retryable is False
    assert assistant_view.retryable is False
    assert assistant_view.attempt is not None
    assert assistant_view.attempt.input_tokens == 10


async def test_read_conversation_returns_none_for_unknown_id(session: AsyncSession) -> None:
    assert await read_conversation(session, uuid.uuid4()) is None


async def test_sequence_counter_reflects_persisted_rows(session: AsyncSession) -> None:
    conversation = await ConversationRepository(session).create(first_message="count me")
    repository = MessageRepository(session)
    await repository.append(conversation_id=conversation.id, role=Role.USER, content="one")
    await repository.append(conversation_id=conversation.id, role=Role.ASSISTANT, content="two")
    await session.commit()

    stored = await session.scalar(
        select(func.count()).select_from(Message).where(Message.conversation_id == conversation.id)
    )
    assert stored == 2


async def test_updated_at_bumps_only_when_messages_are_written(session: AsyncSession) -> None:
    conversation = await ConversationRepository(session).create(first_message="touch me")
    await session.commit()
    initial = conversation.updated_at

    await MessageRepository(session).append(
        conversation_id=conversation.id, role=Role.USER, content="hello"
    )
    await ConversationRepository(session).touch(conversation.id)
    await session.commit()
    await session.refresh(conversation)

    assert conversation.updated_at > initial
    assert conversation.updated_at <= datetime.now(UTC)
