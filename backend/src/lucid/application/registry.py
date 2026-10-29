"""In-process registry of active generations.

Stop is cooperative: the streaming loop checks ``stop_requested`` between events
so it can finalize the attempt and still emit a terminal SSE event. A short
grace timer cancels the task if the provider stalls, in which case the client
sees the connection close and treats it as an interruption.
"""

import asyncio
import uuid
from dataclasses import dataclass, field

STOP_GRACE_SECONDS = 1.5


@dataclass(slots=True)
class ActiveGeneration:
    """Bookkeeping for one in-flight generation."""

    attempt_id: uuid.UUID
    task: asyncio.Task[object] | None
    stop_requested: asyncio.Event = field(default_factory=asyncio.Event)
    cancel_handle: asyncio.TimerHandle | None = None


class GenerationRegistry:
    """Tracks generations owned by this process."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._active: dict[uuid.UUID, ActiveGeneration] = {}

    async def register(self, attempt_id: uuid.UUID) -> ActiveGeneration:
        """Register the current task as the owner of an attempt."""
        async with self._lock:
            entry = ActiveGeneration(attempt_id=attempt_id, task=asyncio.current_task())
            self._active[attempt_id] = entry
            return entry

    async def deregister(self, attempt_id: uuid.UUID) -> None:
        async with self._lock:
            entry = self._active.pop(attempt_id, None)
        if entry is not None and entry.cancel_handle is not None:
            entry.cancel_handle.cancel()

    async def request_stop(self, attempt_id: uuid.UUID) -> bool:
        """Ask a tracked generation to stop. False when it is not tracked."""
        async with self._lock:
            entry = self._active.get(attempt_id)
        if entry is None:
            return False

        entry.stop_requested.set()
        task = entry.task
        if task is not None and not task.done():
            loop = asyncio.get_running_loop()
            entry.cancel_handle = loop.call_later(STOP_GRACE_SECONDS, task.cancel)
        return True

    async def is_active(self, attempt_id: uuid.UUID) -> bool:
        async with self._lock:
            return attempt_id in self._active

    async def cancel_all(self) -> None:
        """Cancel every generation, used at shutdown."""
        async with self._lock:
            entries = list(self._active.values())

        for entry in entries:
            if entry.task is not None and not entry.task.done():
                entry.task.cancel()

    @property
    def size(self) -> int:
        return len(self._active)
