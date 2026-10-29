"""Model catalogue endpoint."""

from httpx import AsyncClient


async def test_lists_the_scripted_provider_in_tests(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/models")

    assert response.status_code == 200
    body = response.json()
    assert body["default_id"] == "fake:fake-model"
    assert [item["id"] for item in body["items"]] == ["fake:fake-model"]
    assert body["items"][0]["provider"] == "fake"


async def test_unknown_model_is_rejected_by_chat(api_client: AsyncClient) -> None:
    response = await api_client.post(
        "/api/chat", json={"content": "hello", "model_id": "nope:nothing"}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "model_not_available"
