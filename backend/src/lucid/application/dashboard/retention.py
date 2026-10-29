"""Delete generation-attempt telemetry older than the retention window.

Conversation history is never touched: only attempt rows are removed, and the
assistant message they point to is kept via ``ON DELETE SET NULL``.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import CursorResult, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lucid.domain.enums import AttemptStatus
from lucid.persistence.tables import GenerationAttempt

logger = logging.getLogger(__name__)

RETENTION_INTERVAL_SECONDS = 24 * 60 * 60


async def delete_expired_attempts(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    retention_days: int,
    now: datetime | None = None,
) -> int:
    """Delete terminal attempts older than the cutoff. Returns the row count."""
    cutoff = (now or datetime.now(UTC)) - timedelta(days=retention_days)
    async with session_factory() as session:
        result = await session.execute(
            delete(GenerationAttempt).where(
                GenerationAttempt.status != AttemptStatus.IN_PROGRESS.value,
                GenerationAttempt.started_at < cutoff,
            )
        )
        await session.commit()

    deleted = result.rowcount if isinstance(result, CursorResult) else 0
    logger.info(
        "telemetry retention",
        extra={"ctx_deleted_attempts": deleted, "ctx_cutoff": cutoff.isoformat()},
    )
    return deleted


async def periodic_retention(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    retention_days: int,
    interval_seconds: int = RETENTION_INTERVAL_SECONDS,
) -> None:
    """Run retention forever, once per interval, without failing the app."""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            await delete_expired_attempts(session_factory, retention_days=retention_days)
        except Exception:
            logger.exception("telemetry retention failed")
