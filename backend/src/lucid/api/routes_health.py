"""Health and readiness endpoints."""

from typing import Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from lucid.persistence.db import check_database

router = APIRouter(tags=["health"])


class LivenessResponse(BaseModel):
    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    database: Literal["ok", "unavailable"]


async def database_reachable() -> bool:
    """Readiness dependency, overridable in tests."""
    return await check_database()


@router.get("/health", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    """Liveness: the process is up. Deliberately checks no dependencies."""
    return LivenessResponse(status="ok")


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness(
    response: Response,
    database_ok: bool = Depends(database_reachable),
) -> ReadinessResponse:
    """Readiness: the process can serve traffic, including database access."""
    if not database_ok:
        response.status_code = 503
        return ReadinessResponse(status="unavailable", database="unavailable")
    return ReadinessResponse(status="ok", database="ok")
