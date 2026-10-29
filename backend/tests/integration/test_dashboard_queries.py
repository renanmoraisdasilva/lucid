"""Deterministic aggregation boundaries for the dashboard queries."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from lucid.application.dashboard.buckets import DashboardRange, window_for
from lucid.domain.enums import AttemptStatus
from lucid.persistence import dashboard_queries
from tests.integration.dashboard_support import seed_attempt, seed_conversation

NOW = datetime(2026, 10, 29, 15, 30, tzinfo=UTC)


async def test_range_includes_start_and_excludes_end(session: AsyncSession) -> None:
    window = window_for(DashboardRange.WEEK, NOW)
    conversation, user = await seed_conversation(session, "Boundary")

    for started_at in (
        window.start - timedelta(seconds=1),
        window.start,
        window.end - timedelta(seconds=1),
        window.end,
    ):
        await seed_attempt(
            session,
            conversation,
            user,
            started_at=started_at,
            status=AttemptStatus.COMPLETED,
        )

    counts = await dashboard_queries.overview_counts(session, window)

    # Inclusive start, exclusive end: two of the four rows are in range.
    assert counts.attempts == 2
    assert counts.completed == 2
