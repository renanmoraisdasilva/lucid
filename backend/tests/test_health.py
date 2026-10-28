"""Health and readiness behaviour."""

from fastapi import FastAPI
from httpx import AsyncClient

from chatbot.api.routes_health import database_reachable


async def _database_available() -> bool:
    return True


async def _database_unavailable() -> bool:
    return False


async def test_liveness_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_liveness_sets_request_id_header(client: AsyncClient) -> None:
    response = await client.get("/api/health")

    assert response.headers["X-Request-ID"]


async def test_request_id_header_is_preserved(client: AsyncClient) -> None:
    response = await client.get("/api/health", headers={"X-Request-ID": "abc-123"})

    assert response.headers["X-Request-ID"] == "abc-123"


async def test_readiness_reports_database_ok(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[database_reachable] = _database_available

    response = await client.get("/api/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_readiness_reports_503_when_database_unavailable(
    app: FastAPI, client: AsyncClient
) -> None:
    app.dependency_overrides[database_reachable] = _database_unavailable

    response = await client.get("/api/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unavailable"}
