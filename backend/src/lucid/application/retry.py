"""Retry policy for provider calls (ADR-005).

Automatic retries happen inside one attempt and only before the first token: once
text has reached the client, retrying would duplicate output. Manual retry is a
separate endpoint that creates a new attempt.
"""

import random
from collections.abc import Callable
from dataclasses import dataclass

from lucid.domain.errors import ProviderError


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Bounded exponential backoff with jitter."""

    max_retries: int = 2
    base_delay_ms: int = 1_000
    max_delay_ms: int = 8_000
    jitter: bool = True

    def is_retryable(self, error: ProviderError, *, has_output: bool) -> bool:
        """Only transient failures with nothing streamed yet are retried."""
        return error.retryable and not has_output

    def delay_seconds(
        self,
        retry_index: int,
        *,
        rand: Callable[[], float] = random.random,
    ) -> float:
        """Delay before the given retry (0-based), capped and optionally jittered."""
        capped_ms = min(self.base_delay_ms * (2**retry_index), self.max_delay_ms)
        seconds = capped_ms / 1000
        if not self.jitter:
            return seconds
        # Full-ish jitter: 50-100% of the computed delay, so retries do not
        # synchronise across clients while staying bounded.
        return seconds * (0.5 + 0.5 * rand())
