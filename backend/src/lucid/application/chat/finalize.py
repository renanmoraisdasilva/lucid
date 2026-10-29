"""Write the terminal state of one generation attempt."""

import asyncio
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lucid.application.chat.telemetry import AttemptTelemetry
from lucid.application.chat.turns import PreparedGeneration
from lucid.domain.enums import AttemptStatus, Role
from lucid.domain.outcome import AttemptOutcome
from lucid.domain.provider import Usage
from lucid.persistence.repositories import (
    AttemptRepository,
    ConversationRepository,
    MessageRepository,
)


@dataclass(frozen=True, slots=True)
class TurnOutcome:
    """What a terminal stream wants to store."""

    status: AttemptStatus
    text: str
    usage: Usage | None = None
    error_code: str | None = None
    error_message: str | None = None
    telemetry: AttemptTelemetry = field(default_factory=AttemptTelemetry)


@dataclass(frozen=True, slots=True)
class FinalizedTurn:
    """What the terminal transaction wrote."""

    status: AttemptStatus
    assistant_message_id: uuid.UUID | None
    content: str


async def finalize(
    session_factory: async_sessionmaker[AsyncSession],
    prepared: PreparedGeneration,
    outcome: TurnOutcome,
) -> FinalizedTurn:
    """Write the terminal state in one transaction."""
    async with session_factory() as session:
        messages = MessageRepository(session)
        attempts = AttemptRepository(session)

        assistant_message_id: uuid.UUID | None = None
        if outcome.text:
            assistant = await messages.append(
                conversation_id=prepared.conversation_id,
                role=Role.ASSISTANT,
                content=outcome.text,
            )
            assistant_message_id = assistant.id
            await ConversationRepository(session).touch(prepared.conversation_id)

        await attempts.finalize(
            prepared.attempt_id,
            _attempt_outcome(outcome, assistant_message_id),
        )
        await session.commit()

    return FinalizedTurn(
        status=outcome.status,
        assistant_message_id=assistant_message_id,
        content=outcome.text,
    )


def _attempt_outcome(
    outcome: TurnOutcome, assistant_message_id: uuid.UUID | None
) -> AttemptOutcome:
    usage = outcome.usage
    return AttemptOutcome(
        status=outcome.status,
        assistant_message_id=assistant_message_id,
        error_code=outcome.error_code,
        error_message=outcome.error_message,
        usage_raw=_usage_raw(usage),
        input_tokens=usage.input_tokens if usage is not None else None,
        output_tokens=usage.output_tokens if usage is not None else None,
        thought_tokens=usage.thought_tokens if usage is not None else None,
        total_tokens=usage.total_tokens if usage is not None else None,
        first_token_at=outcome.telemetry.first_token_at,
        http_status=outcome.telemetry.http_status,
        retry_count=outcome.telemetry.retry_count,
        context_tokens=outcome.telemetry.context_tokens,
    )


async def finalize_after_cancel(
    session_factory: async_sessionmaker[AsyncSession],
    prepared: PreparedGeneration,
    text: str,
    usage: Usage | None,
    telemetry: AttemptTelemetry,
) -> None:
    """Finalize an interrupted attempt while the current task is cancelled."""
    task = asyncio.create_task(
        finalize(
            session_factory,
            prepared,
            TurnOutcome(
                status=AttemptStatus.INTERRUPTED,
                text=text,
                usage=usage,
                error_code="interrupted",
                telemetry=telemetry,
            ),
        )
    )
    with suppress(asyncio.CancelledError):
        await asyncio.shield(task)
    if not task.done():  # pragma: no cover - only if cancelled twice
        task.add_done_callback(lambda _: None)


def _usage_raw(usage: Usage | None) -> dict[str, Any] | None:
    if usage is None or usage.raw is None:
        return None
    return dict(usage.raw)
