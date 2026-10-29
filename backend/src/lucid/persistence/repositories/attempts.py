"""Generation attempt lifecycle metadata."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lucid.domain.enums import AttemptStatus
from lucid.domain.outcome import AttemptOutcome
from lucid.persistence.tables import GenerationAttempt


class AttemptRepository:
    """Generation attempt lifecycle metadata."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        conversation_id: uuid.UUID,
        user_message_id: uuid.UUID,
        provider: str,
        model: str,
    ) -> GenerationAttempt:
        attempt_no = await self.next_attempt_no(user_message_id)
        attempt = GenerationAttempt(
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            attempt_no=attempt_no,
            status=AttemptStatus.IN_PROGRESS.value,
            provider=provider,
            model=model,
        )
        self._session.add(attempt)
        await self._session.flush()
        return attempt

    async def next_attempt_no(self, user_message_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(GenerationAttempt.attempt_no), 0)).where(
                GenerationAttempt.user_message_id == user_message_id
            )
        )
        return int(result.scalar_one()) + 1

    async def get(self, attempt_id: uuid.UUID) -> GenerationAttempt | None:
        return await self._session.get(GenerationAttempt, attempt_id)

    async def get_active_for_conversation(
        self, conversation_id: uuid.UUID
    ) -> GenerationAttempt | None:
        """Return the in-progress attempt, if any."""
        result = await self._session.execute(
            select(GenerationAttempt).where(
                GenerationAttempt.conversation_id == conversation_id,
                GenerationAttempt.status == AttemptStatus.IN_PROGRESS.value,
            )
        )
        return result.scalar_one_or_none()

    async def list_active_for_conversations(
        self, conversation_ids: Sequence[uuid.UUID]
    ) -> Sequence[GenerationAttempt]:
        """Return every in-progress attempt for the given conversations."""
        if not conversation_ids:
            return []
        result = await self._session.execute(
            select(GenerationAttempt).where(
                GenerationAttempt.conversation_id.in_(conversation_ids),
                GenerationAttempt.status == AttemptStatus.IN_PROGRESS.value,
            )
        )
        return list(result.scalars().all())

    async def list_for_conversation(
        self, conversation_id: uuid.UUID
    ) -> Sequence[GenerationAttempt]:
        result = await self._session.execute(
            select(GenerationAttempt)
            .where(GenerationAttempt.conversation_id == conversation_id)
            .order_by(GenerationAttempt.started_at.asc(), GenerationAttempt.attempt_no.asc())
        )
        return list(result.scalars().all())

    async def latest_for_user_message(self, user_message_id: uuid.UUID) -> GenerationAttempt | None:
        result = await self._session.execute(
            select(GenerationAttempt)
            .where(GenerationAttempt.user_message_id == user_message_id)
            .order_by(GenerationAttempt.attempt_no.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def has_completed_for_user_message(self, user_message_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            select(func.count())
            .select_from(GenerationAttempt)
            .where(
                GenerationAttempt.user_message_id == user_message_id,
                GenerationAttempt.status == AttemptStatus.COMPLETED.value,
            )
        )
        return int(result.scalar_one()) > 0

    async def finalize(self, attempt_id: uuid.UUID, outcome: AttemptOutcome) -> None:
        """Move an attempt to a terminal state and record its metadata."""
        await self._session.execute(
            update(GenerationAttempt)
            .where(GenerationAttempt.id == attempt_id)
            .values(
                status=outcome.status.value,
                assistant_message_id=outcome.assistant_message_id,
                error_code=outcome.error_code,
                error_message=outcome.error_message,
                usage_raw=outcome.usage_raw,
                input_tokens=outcome.input_tokens,
                output_tokens=outcome.output_tokens,
                thought_tokens=outcome.thought_tokens,
                total_tokens=outcome.total_tokens,
                first_token_at=outcome.first_token_at,
                http_status=outcome.http_status,
                retry_count=outcome.retry_count,
                context_tokens=outcome.context_tokens,
                completed_at=datetime.now(UTC),
            )
        )
