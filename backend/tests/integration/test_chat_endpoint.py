"""Temporary non-streaming chat endpoint, exercised with the fake provider."""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from lucid.domain.errors import ProviderRateLimited
from lucid.providers.fake import FakeProvider, FakeScript


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


async def test_first_message_creates_a_conversation_and_reply(
    chat_client: AsyncClient,
) -> None:
    response = await chat_client.post("/api/chat", json={"content": "Hello Lucid"})

    assert response.status_code == 200
    body = response.json()
    assert body["content"] == "Fake response."
    assert body["attempt_status"] == "completed"
    assert body["assistant_message_id"]
    assert body["usage"] == {
        "input_tokens": 11,
        "output_tokens": 7,
        "thought_tokens": 0,
        "total_tokens": 18,
    }

    detail = await chat_client.get(f"/api/conversations/{body['conversation_id']}")
    assert detail.status_code == 200
    messages = detail.json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "Hello Lucid"
    assert messages[1]["attempt"]["status"] == "completed"
    assert messages[1]["attempt"]["usage"]["output_tokens"] == 7


async def test_conversation_title_is_derived_from_the_first_message(
    chat_client: AsyncClient,
) -> None:
    response = await chat_client.post(
        "/api/chat", json={"content": "Explain   event sourcing\nbriefly"}
    )
    conversation_id = response.json()["conversation_id"]

    listing = await chat_client.get("/api/conversations")

    assert listing.json()["items"][0]["id"] == conversation_id
    assert listing.json()["items"][0]["title"] == "Explain event sourcing briefly"


async def test_continuing_a_conversation_appends_turns(chat_client: AsyncClient) -> None:
    first = await chat_client.post("/api/chat", json={"content": "First"})
    conversation_id = first.json()["conversation_id"]

    second = await chat_client.post(
        "/api/chat", json={"conversation_id": conversation_id, "content": "Second"}
    )

    assert second.status_code == 200
    assert second.json()["conversation_id"] == conversation_id

    detail = await chat_client.get(f"/api/conversations/{conversation_id}")
    assert [message["role"] for message in detail.json()["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]


async def test_provider_receives_system_prompt_and_full_history(
    chat_client: AsyncClient, fake_provider: FakeProvider
) -> None:
    first = await chat_client.post("/api/chat", json={"content": "First"})
    conversation_id = first.json()["conversation_id"]
    await chat_client.post(
        "/api/chat", json={"conversation_id": conversation_id, "content": "Second"}
    )

    request = fake_provider.requests[-1]

    assert request.system_prompt == "You are a test assistant."
    assert [(message.role.value, message.content) for message in request.messages] == [
        ("user", "First"),
        ("assistant", "Fake response."),
        ("user", "Second"),
    ]


async def test_provider_failure_keeps_the_user_message_retryable(
    chat_client: AsyncClient, fake_provider: FakeProvider
) -> None:
    fake_provider.set_script(
        FakeScript(fail_before_first_token=ProviderRateLimited(detail="quota"))
    )

    response = await chat_client.post("/api/chat", json={"content": "Will fail"})

    assert response.status_code == 429
    body = response.json()
    assert body["error"]["code"] == "provider_rate_limited"
    assert "quota" not in body["error"]["message"]

    listing = await chat_client.get("/api/conversations")
    conversation_id = listing.json()["items"][0]["id"]
    detail = await chat_client.get(f"/api/conversations/{conversation_id}")

    messages = detail.json()["messages"]
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert messages[0]["attempt"]["status"] == "failed"
    assert messages[0]["attempt"]["error_code"] == "provider_rate_limited"
    assert messages[0]["attempt"]["retryable"] is True


async def test_unknown_conversation_returns_404(chat_client: AsyncClient) -> None:
    response = await chat_client.post(
        "/api/chat",
        json={"conversation_id": "0192f3c1-0000-7000-8000-000000000000", "content": "Hi"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "conversation_not_found"


@pytest.mark.parametrize("content", ["", "   ", "x" * 16_001])
async def test_invalid_content_is_rejected(chat_client: AsyncClient, content: str) -> None:
    response = await chat_client.post("/api/chat", json={"content": content})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
