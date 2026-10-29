"""HTTP contract for the streaming chat endpoints.

ASGITransport buffers the response body, so these tests assert the *sequence* of
frames. Incremental delivery and cancellation are covered in
``test_streaming_service.py``.
"""

import json
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lucid.domain.enums import AttemptStatus, Role
from lucid.domain.errors import ProviderRateLimited
from lucid.domain.outcome import AttemptOutcome
from lucid.persistence.repositories import (
    AttemptRepository,
    ConversationRepository,
    MessageRepository,
)
from lucid.providers.fake import FakeProvider, FakeScript

TERMINAL = {"done", "error"}


def parse_frames(body: str) -> list[tuple[str, dict[str, object]]]:
    frames: list[tuple[str, dict[str, object]]] = []
    for block in body.split("\n\n"):
        if not block.strip() or block.lstrip().startswith(":"):
            continue
        event: str | None = None
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line.removeprefix("event: ")
            elif line.startswith("data: "):
                data_lines.append(line.removeprefix("data: "))
        if event is not None:
            frames.append((event, json.loads("\n".join(data_lines))))
    return frames


@pytest.fixture
def fake_provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
async def chat_client(app: FastAPI, fake_provider: FakeProvider) -> AsyncIterator[AsyncClient]:
    app.state.provider = fake_provider
    app.state.system_prompt = "You are a test assistant."
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


async def test_success_stream_streams_meta_deltas_usage_and_done(
    chat_client: AsyncClient,
) -> None:
    response = await chat_client.post("/api/chat", json={"content": "Hello Lucid"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-accel-buffering"] == "no"

    frames = parse_frames(response.text)
    names = [name for name, _ in frames]

    assert names[0] == "meta"
    assert names[-1] == "done"
    assert sum(1 for name in names if name in TERMINAL) == 1

    deltas = [data["text"] for name, data in frames if name == "delta"]
    assert deltas == ["Fake ", "response", "."]

    usage = next(data for name, data in frames if name == "usage")
    assert usage == {
        "input_tokens": 11,
        "output_tokens": 7,
        "thought_tokens": 0,
        "total_tokens": 18,
    }

    done = frames[-1][1]
    assert done["status"] == "completed"
    assert done["finish_reason"] == "stop"
    assert done["assistant_message_id"]


async def test_meta_ids_match_persisted_records(chat_client: AsyncClient) -> None:
    response = await chat_client.post("/api/chat", json={"content": "Explain SSE"})

    meta = parse_frames(response.text)[0][1]
    assert meta["is_new_conversation"] is True

    detail = await chat_client.get(f"/api/conversations/{meta['conversation_id']}")
    body = detail.json()

    assert body["title"] == "Explain SSE"
    assert body["messages"][0]["id"] == meta["user_message_id"]
    assert [message["role"] for message in body["messages"]] == ["user", "assistant"]
    assert body["messages"][1]["attempt"]["status"] == "completed"
    assert body["active_attempt_id"] is None


async def test_provider_failure_emits_terminal_error_and_keeps_the_message(
    chat_client: AsyncClient, fake_provider: FakeProvider
) -> None:
    fake_provider.set_script(
        FakeScript(fail_before_first_token=ProviderRateLimited(detail="quota exceeded"))
    )

    response = await chat_client.post("/api/chat", json={"content": "Will fail"})
    frames = parse_frames(response.text)

    assert [name for name, _ in frames] == ["meta", "error"]
    error = frames[-1][1]
    assert error["code"] == "provider_rate_limited"
    assert error["retryable"] is True
    assert "quota exceeded" not in str(error["message"])

    meta = frames[0][1]
    detail = await chat_client.get(f"/api/conversations/{meta['conversation_id']}")
    messages = detail.json()["messages"]
    assert len(messages) == 1
    assert messages[0]["attempt"]["status"] == "failed"
    assert messages[0]["attempt"]["retryable"] is True


async def test_message_while_generating_returns_409(
    chat_client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    async with session_factory() as session:
        conversation = await ConversationRepository(session).create(first_message="Busy")
        user_message = await MessageRepository(session).append(
            conversation_id=conversation.id, role=Role.USER, content="Busy"
        )
        active = await AttemptRepository(session).create(
            conversation_id=conversation.id,
            user_message_id=user_message.id,
            provider="fake",
            model="fake-model",
        )
        await session.commit()

    response = await chat_client.post(
        "/api/chat", json={"conversation_id": str(conversation.id), "content": "Again"}
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "generation_in_progress"
    assert body["error"]["details"]["attempt_id"] == str(active.id)


async def test_unknown_conversation_returns_404(chat_client: AsyncClient) -> None:
    response = await chat_client.post(
        "/api/chat",
        json={"conversation_id": "0192f3c1-0000-7000-8000-000000000000", "content": "Hi"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "conversation_not_found"


async def test_retry_reuses_the_user_message(
    chat_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        conversation = await ConversationRepository(session).create(first_message="Retry me")
        user_message = await MessageRepository(session).append(
            conversation_id=conversation.id, role=Role.USER, content="Retry me"
        )
        failed = await AttemptRepository(session).create(
            conversation_id=conversation.id,
            user_message_id=user_message.id,
            provider="fake",
            model="fake-model",
        )
        await AttemptRepository(session).finalize(
            failed.id,
            AttemptOutcome(status=AttemptStatus.FAILED, error_code="provider_unavailable"),
        )
        await session.commit()
        conversation_id = conversation.id
        user_message_id = user_message.id

    response = await chat_client.post(
        f"/api/conversations/{conversation_id}/messages/{user_message_id}/retry"
    )

    assert response.status_code == 200
    done = parse_frames(response.text)[-1][1]
    assert done["status"] == "completed"

    detail = await chat_client.get(f"/api/conversations/{conversation_id}")
    messages = detail.json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["id"] == str(user_message_id)

    async with session_factory() as session:
        attempts = await AttemptRepository(session).list_for_conversation(conversation_id)
    assert [(attempt.attempt_no, attempt.status) for attempt in attempts] == [
        (1, "failed"),
        (2, "completed"),
    ]


async def test_retry_after_success_returns_409(
    chat_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    response = await chat_client.post("/api/chat", json={"content": "Already answered"})
    meta = parse_frames(response.text)[0][1]

    retry = await chat_client.post(
        f"/api/conversations/{meta['conversation_id']}/messages/{meta['user_message_id']}/retry"
    )

    assert retry.status_code == 409
    assert retry.json()["error"]["code"] == "generation_already_completed"


async def test_stop_is_idempotent_for_terminal_attempt(
    chat_client: AsyncClient,
) -> None:
    response = await chat_client.post("/api/chat", json={"content": "Done already"})
    meta = parse_frames(response.text)[0][1]

    stop = await chat_client.post(
        f"/api/conversations/{meta['conversation_id']}/generations/{meta['attempt_id']}/stop"
    )

    assert stop.status_code == 202
    body = stop.json()
    assert body["status"] == "completed"
    assert body["stop_requested"] is False


async def test_stop_untracked_attempt_marks_it_interrupted(
    chat_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        conversation = await ConversationRepository(session).create(first_message="Orphan")
        user_message = await MessageRepository(session).append(
            conversation_id=conversation.id, role=Role.USER, content="Orphan"
        )
        attempt = await AttemptRepository(session).create(
            conversation_id=conversation.id,
            user_message_id=user_message.id,
            provider="fake",
            model="fake-model",
        )
        await session.commit()
        conversation_id = conversation.id
        attempt_id = attempt.id

    stop = await chat_client.post(
        f"/api/conversations/{conversation_id}/generations/{attempt_id}/stop"
    )

    assert stop.status_code == 202
    assert stop.json()["status"] == "interrupted"

    async with session_factory() as session:
        stored = await AttemptRepository(session).get(attempt_id)
    assert stored is not None
    assert stored.status == "interrupted"
    assert stored.error_code == "cancelled_untracked"


async def test_stop_unknown_attempt_returns_404(chat_client: AsyncClient) -> None:
    response = await chat_client.post(
        "/api/conversations/0192f3c1-0000-7000-8000-000000000000"
        "/generations/0192f3c1-0000-7000-8000-000000000001/stop"
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "attempt_not_found"


@pytest.mark.parametrize("content", ["", "   ", "x" * 16_001])
async def test_invalid_content_is_rejected(chat_client: AsyncClient, content: str) -> None:
    response = await chat_client.post("/api/chat", json={"content": content})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
