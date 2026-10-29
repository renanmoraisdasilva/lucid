"""Overview aggregates for the dashboard."""

from typing import Any

from sqlalchemy import and_, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from lucid.application.dashboard.buckets import DashboardWindow
from lucid.application.dashboard.query_rows import OverviewCounts
from lucid.domain.enums import AttemptStatus, Role
from lucid.persistence.dashboard_sql import (
    int_value,
    optional_int,
    range_filter,
    terminal_range,
)
from lucid.persistence.tables import Conversation, GenerationAttempt, Message


async def _conversation_counts(
    session: AsyncSession, window: DashboardWindow
) -> tuple[int, int, int]:
    message_range = and_(
        Message.created_at >= window.start,
        Message.created_at < window.end,
    )
    active = int_value(
        await session.scalar(
            select(func.count(distinct(Message.conversation_id))).where(message_range)
        )
    )
    new = int_value(
        await session.scalar(
            select(func.count(Conversation.id)).where(
                Conversation.created_at >= window.start,
                Conversation.created_at < window.end,
            )
        )
    )
    user_messages = int_value(
        await session.scalar(
            select(func.count(Message.id)).where(
                message_range,
                Message.role == Role.USER.value,
            )
        )
    )
    return active, new, user_messages


async def _attempt_aggregates(session: AsyncSession, window: DashboardWindow) -> Any:
    return (
        await session.execute(
            select(
                func.count(GenerationAttempt.id).label("attempts"),
                func.count(GenerationAttempt.id)
                .filter(GenerationAttempt.status == AttemptStatus.COMPLETED.value)
                .label("completed"),
                func.count(GenerationAttempt.id)
                .filter(GenerationAttempt.status == AttemptStatus.FAILED.value)
                .label("failed"),
                func.count(GenerationAttempt.id)
                .filter(GenerationAttempt.status == AttemptStatus.INTERRUPTED.value)
                .label("interrupted"),
                func.sum(GenerationAttempt.input_tokens).label("input_tokens"),
                func.sum(GenerationAttempt.output_tokens).label("output_tokens"),
                func.count(GenerationAttempt.input_tokens).label("input_samples"),
                func.count(GenerationAttempt.output_tokens).label("output_samples"),
                func.count(GenerationAttempt.id)
                .filter(
                    or_(
                        GenerationAttempt.input_tokens.is_(None),
                        GenerationAttempt.output_tokens.is_(None),
                    )
                )
                .label("missing_usage"),
            ).where(terminal_range(window))
        )
    ).one()


async def _in_progress_count(session: AsyncSession, window: DashboardWindow) -> int:
    return int_value(
        await session.scalar(
            select(func.count(GenerationAttempt.id)).where(
                range_filter(window),
                GenerationAttempt.status == AttemptStatus.IN_PROGRESS.value,
            )
        )
    )


async def overview_counts(session: AsyncSession, window: DashboardWindow) -> OverviewCounts:
    """Conversation, message and terminal-attempt aggregates."""
    active, new, user_messages = await _conversation_counts(session, window)
    row = await _attempt_aggregates(session, window)
    in_progress = await _in_progress_count(session, window)

    return OverviewCounts(
        conversations_active=active,
        conversations_new=new,
        user_messages=user_messages,
        attempts=int_value(row.attempts),
        completed=int_value(row.completed),
        failed=int_value(row.failed),
        interrupted=int_value(row.interrupted),
        in_progress=in_progress,
        input_tokens=optional_int(row.input_tokens),
        output_tokens=optional_int(row.output_tokens),
        input_samples=int_value(row.input_samples),
        output_samples=int_value(row.output_samples),
        missing_usage=int_value(row.missing_usage),
    )
