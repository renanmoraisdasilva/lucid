"""Startup recovery for attempts stranded by an unexpected process exit.

Partial text is only written at terminal state, so a crash leaves an
``in_progress`` attempt with no assistant message. Marking it interrupted keeps
the conversation usable and unsticks the "one active generation" invariant.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lucid.domain.enums import AttemptStatus
from lucid.persistence.tables import GenerationAttempt

logger = logging.getLogger(__name__)


async def reconcile_stale_attempts(
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    """Mark every in-progress attempt interrupted. Returns how many changed."""
    async with session_factory() as session:
        result = await session.execute(
            update(GenerationAttempt)
            .where(GenerationAttempt.status == AttemptStatus.IN_PROGRESS.value)
            .values(
                status=AttemptStatus.INTERRUPTED.value,
                error_code="process_restart",
                completed_at=datetime.now(UTC),
            )
        )
        await session.commit()

    count = int(getattr(result, "rowcount", 0) or 0)
    if count:
        logger.warning(
            "reconciled stale generation attempts",
            extra={"ctx_count": count},
        )
    return count
