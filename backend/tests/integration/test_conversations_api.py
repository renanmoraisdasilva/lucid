"""HTTP contract for the conversation endpoints."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from lucid.domain.enums import AttemptStatus, Role
from lucid.domain.outcome import AttemptOutcome
from lucid.persistence.repositories import (
    AttemptRepository,
    ConversationRepository,
    MessageRepository,
)
from lucid.persistence.tables import Conversation


async def _seed_conversations(session: AsyncSession, count: int) -> list[Conversation]:
    created: list[Conversation] = []
    for index in range(count):
        conversation = await ConversationRepository(session).create(
            first_message=f"question {index}"
        )
        await session.commit()
        created.append(conversation)
    return created


async def test_list_is_empty_initially(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/conversations")

    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None, "has_more": False}


async def test_list_returns_newest_first(api_client: AsyncClient, session: AsyncSession) -> None:
    created = await _seed_conversations(session, 3)

    response = await api_client.get("/api/conversations")

    body = response.json()
    assert [item["id"] for item in body["items"]] == [
        str(conversation.id) for conversation in reversed(created)
    ]
    assert body["items"][0]["title"] == "question 2"
    assert body["items"][0]["active_attempt_id"] is None


async def test_list_paginates_through_cursor(
    api_client: AsyncClient, session: AsyncSession
) -> None:
    await _seed_conversations(session, 3)

    first = await api_client.get("/api/conversations", params={"limit": 2})
    first_body = first.json()
    assert first_body["has_more"] is True
    assert first_body["next_cursor"]

    second = await api_client.get(
        "/api/conversations", params={"limit": 2, "cursor": first_body["next_cursor"]}
    )
    second_body = second.json()

    assert second_body["has_more"] is False
    assert second_body["next_cursor"] is None
    assert len(second_body["items"]) == 1
    assert {item["id"] for item in second_body["items"]}.isdisjoint(
        {item["id"] for item in first_body["items"]}
    )


async def test_invalid_cursor_returns_a_stable_error(
    api_client: AsyncClient,
) -> None:
    response = await api_client.get("/api/conversations", params={"cursor": "garbage"})

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "invalid_cursor"
    assert body["error"]["message"]


async def test_page_size_is_validated(api_client: AsyncClient) -> None:
    too_small = await api_client.get("/api/conversations", params={"limit": 0})
    too_large = await api_client.get("/api/conversations", params={"limit": 21})

    for response in (too_small, too_large):
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
        assert response.json()["error"]["details"]["fields"]


async def test_get_unknown_conversation_returns_404(api_client: AsyncClient) -> None:
    response = await api_client.get(f"/api/conversations/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "conversation_not_found"


async def test_get_malformed_id_returns_validation_error(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/conversations/not-a-uuid")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_detail_returns_messages_in_sequence_with_attempt_metadata(
    api_client: AsyncClient, session: AsyncSession
) -> None:
    conversation = await ConversationRepository(session).create(first_message="hello")
    user_message = await MessageRepository(session).append(
        conversation_id=conversation.id, role=Role.USER, content="hello"
    )
    attempt = await AttemptRepository(session).create(
        conversation_id=conversation.id,
        user_message_id=user_message.id,
        provider="fake",
        model="fake-model",
    )
    assistant_message = await MessageRepository(session).append(
        conversation_id=conversation.id, role=Role.ASSISTANT, content="hi there"
    )
    await AttemptRepository(session).finalize(
        attempt.id,
        AttemptOutcome(
            status=AttemptStatus.COMPLETED,
            assistant_message_id=assistant_message.id,
            input_tokens=11,
            output_tokens=90,
            total_tokens=101,
        ),
    )
    await session.commit()

    response = await api_client.get(f"/api/conversations/{conversation.id}")

    assert response.status_code == 200
    body = response.json()
    assert [message["seq"] for message in body["messages"]] == [1, 2]
    assert [message["role"] for message in body["messages"]] == ["user", "assistant"]
    assistant = body["messages"][1]
    assert assistant["attempt"]["status"] == "completed"
    assert assistant["attempt"]["usage"] == {
        "input_tokens": 11,
        "output_tokens": 90,
        "thought_tokens": None,
        "total_tokens": 101,
    }
    assert assistant["attempt"]["retryable"] is False
    assert body["active_attempt_id"] is None


async def test_detail_reports_retryable_failed_generation(
    api_client: AsyncClient, session: AsyncSession
) -> None:
    conversation = await ConversationRepository(session).create(first_message="poison")
    user_message = await MessageRepository(session).append(
        conversation_id=conversation.id, role=Role.USER, content="poison"
    )
    attempt = await AttemptRepository(session).create(
        conversation_id=conversation.id,
        user_message_id=user_message.id,
        provider="fake",
        model="fake-model",
    )
    await AttemptRepository(session).finalize(
        attempt.id,
        AttemptOutcome(
            status=AttemptStatus.FAILED,
            error_code="provider_unavailable",
            error_message="The model is unavailable.",
        ),
    )
    await session.commit()

    response = await api_client.get(f"/api/conversations/{conversation.id}")

    body = response.json()
    assert len(body["messages"]) == 1
    user = body["messages"][0]
    assert user["attempt"]["status"] == "failed"
    assert user["attempt"]["retryable"] is True
    assert user["attempt"]["usage"] is None


async def test_detail_reports_non_retryable_context_failure(
    api_client: AsyncClient, session: AsyncSession
) -> None:
    conversation = await ConversationRepository(session).create(first_message="too big")
    user_message = await MessageRepository(session).append(
        conversation_id=conversation.id, role=Role.USER, content="too big"
    )
    attempt = await AttemptRepository(session).create(
        conversation_id=conversation.id,
        user_message_id=user_message.id,
        provider="fake",
        model="fake-model",
    )
    await AttemptRepository(session).finalize(
        attempt.id,
        AttemptOutcome(
            status=AttemptStatus.FAILED,
            error_code="context_too_large",
            error_message="Too much context.",
        ),
    )
    await session.commit()

    response = await api_client.get(f"/api/conversations/{conversation.id}")

    assert response.json()["messages"][0]["attempt"]["retryable"] is False


async def test_detail_reports_active_attempt(
    api_client: AsyncClient, session: AsyncSession
) -> None:
    conversation = await ConversationRepository(session).create(first_message="working")
    user_message = await MessageRepository(session).append(
        conversation_id=conversation.id, role=Role.USER, content="working"
    )
    attempt = await AttemptRepository(session).create(
        conversation_id=conversation.id,
        user_message_id=user_message.id,
        provider="fake",
        model="fake-model",
    )
    await session.commit()

    detail = await api_client.get(f"/api/conversations/{conversation.id}")
    listing = await api_client.get("/api/conversations")

    assert detail.json()["active_attempt_id"] == str(attempt.id)
    assert listing.json()["items"][0]["active_attempt_id"] == str(attempt.id)


async def test_delete_removes_the_conversation(
    api_client: AsyncClient, session: AsyncSession
) -> None:
    conversation = await ConversationRepository(session).create(first_message="delete me")
    await session.commit()

    deleted = await api_client.delete(f"/api/conversations/{conversation.id}")
    fetched = await api_client.get(f"/api/conversations/{conversation.id}")
    listing = await api_client.get("/api/conversations")

    assert deleted.status_code == 204
    assert deleted.content == b""
    assert fetched.status_code == 404
    assert listing.json()["items"] == []


async def test_delete_unknown_conversation_returns_404(api_client: AsyncClient) -> None:
    response = await api_client.delete(f"/api/conversations/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "conversation_not_found"


async def test_error_envelope_shape_is_consistent(api_client: AsyncClient) -> None:
    response = await api_client.get(f"/api/conversations/{uuid.uuid4()}")

    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
