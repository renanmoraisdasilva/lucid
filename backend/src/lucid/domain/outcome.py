"""Terminal metadata for one generation attempt.

The dataclass keeps repository calls small as telemetry grows. Adding a field here
is cheaper and safer than adding another keyword argument to every caller.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from lucid.domain.enums import AttemptStatus


@dataclass(frozen=True, slots=True)
class AttemptOutcome:
    """Everything the attempt row needs when it reaches a terminal state."""

    status: AttemptStatus
    assistant_message_id: uuid.UUID | None = None
    error_code: str | None = None
    error_message: str | None = None
    usage_raw: dict[str, Any] | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    thought_tokens: int | None = None
    total_tokens: int | None = None
    first_token_at: datetime | None = None
    http_status: int | None = None
    retry_count: int = 0
    context_tokens: int | None = None
