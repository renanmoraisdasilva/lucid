"""Domain enumerations shared by the application, persistence, and API layers."""

from enum import StrEnum


class Role(StrEnum):
    """Who produced a message."""

    USER = "user"
    ASSISTANT = "assistant"


class AttemptStatus(StrEnum):
    """Lifecycle of one generation attempt."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"

    @property
    def is_terminal(self) -> bool:
        """True once the attempt can no longer change."""
        return self is not AttemptStatus.IN_PROGRESS
