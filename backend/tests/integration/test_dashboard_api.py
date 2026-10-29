"""Dashboard aggregation and response contract."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import lucid.api.routes_dashboard as routes_dashboard
from lucid.config import Settings
from lucid.domain.enums import AttemptStatus
from tests.integration.dashboard_support import seed_attempt, seed_conversation


async def _seed_populated(session: AsyncSession, now: datetime) -> None:
    conversation, user = await seed_conversation(session, "Dashboard test")
    await seed_attempt(
        session,
        conversation,
        user,
        started_at=now - timedelta(hours=1),
        status=AttemptStatus.COMPLETED,
        first_token_at=now - timedelta(hours=1) + timedelta(milliseconds=400),
        completed_at=now - timedelta(hours=1) + timedelta(milliseconds=2600),
        input_tokens=1000,
        output_tokens=200,
        context_tokens=1000,
        http_status=200,
        with_assistant=True,
    )
    await seed_attempt(
        session,
        conversation,
        user,
        started_at=now - timedelta(hours=2),
        status=AttemptStatus.FAILED,
        http_status=429,
        retry_count=2,
        error_code="provider_rate_limited",
    )
    await seed_attempt(
        session,
        conversation,
        user,
        started_at=now - timedelta(hours=30),
        status=AttemptStatus.INTERRUPTED,
        first_token_at=now - timedelta(hours=30) + timedelta(milliseconds=500),
        completed_at=now - timedelta(hours=30) + timedelta(milliseconds=1200),
        http_status=200,
    )
    await seed_attempt(
        session,
        conversation,
        user,
        started_at=now - timedelta(hours=3),
        status=None,
    )


async def test_dashboard_aggregates_and_excludes_in_progress(
    api_client: AsyncClient,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings()
    settings.pricing_input_usd_per_million = None
    settings.pricing_output_usd_per_million = None
    monkeypatch.setattr(routes_dashboard, "get_settings", lambda: settings)

    now = datetime.now(UTC)
    await _seed_populated(session, now)

    response = await api_client.get("/api/dashboard")
    assert response.status_code == 200
    body = response.json()
    overview = body["overview"]

    assert body["range"] == "7d"
    assert body["bucket"] == "day"
    assert overview["conversations_active"] == 1
    assert overview["conversations_new"] == 1
    assert overview["user_messages"] == 1
    assert overview["attempts"] == 3
    assert overview["completed"] == 1
    assert overview["failed"] == 1
    assert overview["interrupted"] == 1
    assert overview["in_progress"] == 1
    assert overview["success_rate"] == pytest.approx(1 / 3, abs=1e-4)
    assert overview["input_tokens"] == 1000
    assert overview["output_tokens"] == 200
    assert overview["usage_partial"] is True
    assert overview["pricing"]["available"] is False

    assert len(body["trend"]) == 7
    assert sum(point["attempts"] for point in body["trend"]) == 3
    assert body["latency"]["ttft"]["samples"] == 2
    assert body["latency"]["ttft"]["p50_ms"] is not None
    assert body["latency"]["ttft"]["p95_ms"] is None
    assert body["latency"]["duration"]["samples"] == 3

    assert len(body["recent"]) == 3
    assert body["recent"][0]["status"] == "completed"
    assert body["recent"][0]["conversation_title"] == "Dashboard test"
    assert body["recent"][0]["ttft_ms"] == 400.0
    assert body["recent"][0]["duration_ms"] == 2600.0
    assert "content" not in body["recent"][0]


async def test_24h_excludes_older_attempts(
    api_client: AsyncClient,
    session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    await _seed_populated(session, now)

    body = (await api_client.get("/api/dashboard?range=24h")).json()

    assert body["range"] == "24h"
    assert body["bucket"] == "hour"
    assert len(body["trend"]) == 24
    assert body["overview"]["attempts"] == 2
    assert body["overview"]["interrupted"] == 0
    assert body["overview"]["in_progress"] == 1


async def test_dashboard_estimates_cost(
    api_client: AsyncClient,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings()
    settings.pricing_input_usd_per_million = 0.30
    settings.pricing_output_usd_per_million = 2.50
    settings.pricing_free_tier = True
    monkeypatch.setattr(routes_dashboard, "get_settings", lambda: settings)

    now = datetime.now(UTC)
    conversation, user = await seed_conversation(session, "Cost test")
    await seed_attempt(
        session,
        conversation,
        user,
        started_at=now - timedelta(minutes=5),
        status=AttemptStatus.COMPLETED,
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        with_assistant=True,
    )

    overview = (await api_client.get("/api/dashboard?range=7d")).json()["overview"]

    assert overview["estimated_cost_usd"] == 2.8
    assert overview["pricing"] == {
        "available": True,
        "free_tier": True,
        "input_usd_per_million": 0.3,
        "output_usd_per_million": 2.5,
    }


async def test_empty_range_is_explicit(api_client: AsyncClient) -> None:
    body = (await api_client.get("/api/dashboard?range=24h")).json()
    overview = body["overview"]

    assert overview["attempts"] == 0
    assert overview["success_rate"] is None
    assert overview["input_tokens"] == 0
    assert overview["output_tokens"] == 0
    assert overview["usage_partial"] is False
    assert len(body["trend"]) == 24
    assert all(point["attempts"] == 0 for point in body["trend"])
    assert body["latency"]["ttft"] == {"p50_ms": None, "p95_ms": None, "samples": 0}
    assert body["recent"] == []


async def test_invalid_range_uses_the_error_envelope(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/dashboard?range=90d")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_recent_is_limited_to_25(
    api_client: AsyncClient,
    session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    conversation, user = await seed_conversation(session, "Many attempts")
    attempts = [
        await seed_attempt(
            session,
            conversation,
            user,
            started_at=now - timedelta(minutes=index),
            status=AttemptStatus.COMPLETED,
        )
        for index in range(26)
    ]

    body = (await api_client.get("/api/dashboard?range=7d")).json()
    returned = {item["attempt_id"] for item in body["recent"]}

    assert len(body["recent"]) == 25
    assert returned == {str(attempt.id) for attempt in attempts[:25]}
