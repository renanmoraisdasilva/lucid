"""The adapter strips provider retry hints so the SDK cannot sleep for hours."""

import httpx

from lucid.providers.gemini import RetryAfterStrippingTransport


async def test_retry_hint_headers_are_removed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"Retry-After": "39340", "retry-after-ms": "5", "X-Other": "kept"},
            json={"error": {"message": "quota"}},
        )

    transport = RetryAfterStrippingTransport(httpx.MockTransport(handler))
    async with httpx.AsyncClient(transport=transport) as client:
        response = await client.post("https://example.test/v1beta/interactions")

    assert response.status_code == 429
    assert "retry-after" not in response.headers
    assert "retry-after-ms" not in response.headers
    assert response.headers["x-other"] == "kept"


async def test_other_responses_pass_through() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    transport = RetryAfterStrippingTransport(httpx.MockTransport(handler))
    async with httpx.AsyncClient(transport=transport) as client:
        response = await client.get("https://example.test/")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
