"""Recent-attempt query for the dashboard."""

import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lucid.application.dashboard.buckets import DashboardWindow
from lucid.application.dashboard.query_rows import RecentRow
from lucid.persistence.dashboard_sql import int_value, optional_int, terminal_range
from lucid.persistence.tables import Conversation, GenerationAttempt

RECENT_LIMIT = 25


async def recent(session: AsyncSession, window: DashboardWindow) -> list[RecentRow]:
    """The latest terminal attempts in the window, newest first."""
    rows = (
        await session.execute(
            select(
                GenerationAttempt.id.label("attempt_id"),
                GenerationAttempt.started_at,
                GenerationAttempt.conversation_id,
                Conversation.title.label("conversation_title"),
                GenerationAttempt.status,
                GenerationAttempt.model,
                GenerationAttempt.attempt_no,
                GenerationAttempt.retry_count,
                GenerationAttempt.input_tokens,
                GenerationAttempt.output_tokens,
                GenerationAttempt.first_token_at,
                GenerationAttempt.completed_at,
                GenerationAttempt.http_status,
                GenerationAttempt.context_tokens,
                GenerationAttempt.error_code,
                GenerationAttempt.error_message,
            )
            .join(Conversation, Conversation.id == GenerationAttempt.conversation_id)
            .where(terminal_range(window))
            .order_by(GenerationAttempt.started_at.desc(), GenerationAttempt.id.desc())
            .limit(RECENT_LIMIT)
        )
    ).all()

    return [
        RecentRow(
            attempt_id=cast(uuid.UUID, row.attempt_id),
            started_at=cast(datetime, row.started_at),
            conversation_id=cast(uuid.UUID, row.conversation_id),
            conversation_title=str(row.conversation_title),
            status=str(row.status),
            model=str(row.model),
            attempt_no=int_value(row.attempt_no),
            retry_count=int_value(row.retry_count),
            input_tokens=optional_int(row.input_tokens),
            output_tokens=optional_int(row.output_tokens),
            first_token_at=cast(datetime | None, row.first_token_at),
            completed_at=cast(datetime | None, row.completed_at),
            http_status=optional_int(row.http_status),
            context_tokens=optional_int(row.context_tokens),
            error_code=cast(str | None, row.error_code),
            error_message=cast(str | None, row.error_message),
        )
        for row in rows
    ]
