"""Provider stream cleanup is bounded and never blocks a finished response."""

import asyncio
import time

from lucid.providers.streams import close_stream


class HangingStream:
    """Mimics an SDK stream whose close() waits for the connection to drain."""

    def async_close_called(self) -> bool:  # pragma: no cover - helper
        return False

    async def close(self) -> None:
        await asyncio.Event().wait()


class FailingStream:
    async def close(self) -> None:
        raise RuntimeError("close failed")


class StatelessStream:
    pass


async def test_close_is_timeout_bounded() -> None:
    started = time.perf_counter()

    await close_stream(HangingStream(), limit=0.05)

    assert time.perf_counter() - started < 1.0


async def test_close_errors_are_swallowed() -> None:
    await close_stream(FailingStream(), limit=0.05)


async def test_stream_without_close_is_ignored() -> None:
    await close_stream(StatelessStream(), limit=0.05)
