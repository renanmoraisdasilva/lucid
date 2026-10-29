"""Timeout-bounded helpers for provider stream cleanup."""

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from typing import Final, cast

CLOSE_TIMEOUT_SECONDS: Final = 2.0


async def close_stream(stream: object, *, limit: float = CLOSE_TIMEOUT_SECONDS) -> None:
    """Close a provider stream without ever blocking the response.

    Some SDK streams keep the HTTP connection open after their terminal event.
    Awaiting ``close()`` unbounded was observed hanging a finished generation, so
    the response never sent its terminal event. Closing is best-effort: a timeout
    or an error is swallowed, and the caller proceeds.
    """
    close = getattr(stream, "close", None)
    if not callable(close):
        return
    closer = cast("Callable[[], Awaitable[None]]", close)
    with contextlib.suppress(Exception):
        await asyncio.wait_for(closer(), timeout=limit)
