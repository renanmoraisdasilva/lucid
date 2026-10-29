"""Server-Sent Events framing.

One place builds frames so every stream has the same shape, and so the terminal
event contract stays visible.
"""

import json
from collections.abc import Mapping
from typing import Final

SSE_MEDIA_TYPE: Final = "text/event-stream"

SSE_HEADERS: Final[dict[str, str]] = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

TERMINAL_EVENTS: Final = frozenset({"done", "error"})


def encode_event(event: str, data: Mapping[str, object]) -> str:
    """Encode one named SSE event with a single JSON data line."""
    payload = json.dumps(data, separators=(",", ":"), default=str)
    return f"event: {event}\ndata: {payload}\n\n"
