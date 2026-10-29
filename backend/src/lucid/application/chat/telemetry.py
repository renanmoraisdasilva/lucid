"""Mutable telemetry captured during one generation attempt."""

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(slots=True)
class AttemptTelemetry:
    """Fields that are only known while the provider stream is running.

    The object is created at attempt start, updated as events arrive, and read
    once by the terminal transaction. Nothing is written before terminal state.
    """

    first_token_at: datetime | None = None
    http_status: int | None = None
    retry_count: int = 0
    context_tokens: int | None = None

    def mark_first_token(self) -> None:
        """Record the first text delta exactly once."""
        if self.first_token_at is None:
            self.first_token_at = datetime.now(UTC)

    def mark_retry(self) -> None:
        self.retry_count += 1
