"""Short-lived rate-limit cooldown shared by the chat requests.

When the provider answers 429 it usually says how long to wait. Instead of
immediately calling it again (and making the limit worse), the next requests fail
fast with the remaining time until the provider is likely to accept traffic.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field

DEFAULT_COOLDOWN_SECONDS = 20.0


@dataclass
class RateLimitCooldown:
    """Tracks when the provider may be called again."""

    clock: Callable[[], float] = field(default=time.monotonic)
    _until: float = 0.0
    _reason: str | None = None

    def remaining(self) -> float:
        """Seconds until traffic is allowed again (0 when free)."""
        return max(0.0, self._until - self.clock())

    @property
    def reason(self) -> str | None:
        """The provider's message from the failure that started the cooldown."""
        return self._reason

    def record(self, seconds: float | None, *, reason: str | None = None) -> None:
        """Start (or extend) a cooldown for the given number of seconds."""
        duration = DEFAULT_COOLDOWN_SECONDS if seconds is None else max(seconds, 0.0)
        self._until = max(self._until, self.clock() + duration)
        if reason is not None:
            self._reason = reason

    def clear(self) -> None:
        self._until = 0.0
        self._reason = None
