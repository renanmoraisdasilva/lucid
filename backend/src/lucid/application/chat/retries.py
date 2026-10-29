"""Provider streaming with bounded automatic retries inside one attempt."""

import asyncio
import logging
import uuid
from collections.abc import AsyncGenerator
from contextlib import suppress
from dataclasses import dataclass

from lucid.application.chat.telemetry import AttemptTelemetry
from lucid.application.retry import RetryPolicy
from lucid.domain.errors import FirstTokenTimeout, ProviderError, ProviderRateLimited
from lucid.domain.provider import (
    ChatProvider,
    GenerationRequest,
    ProviderEvent,
    StreamCompleted,
    TextDelta,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RetryLoop:
    """State shared by the retry loop and the bounded stream."""

    policy: RetryPolicy
    stop_event: asyncio.Event
    attempt_id: uuid.UUID
    telemetry: AttemptTelemetry
    first_token_timeout: float | None = None


async def stream_with_retries(
    provider: ChatProvider,
    request: GenerationRequest,
    loop: RetryLoop,
) -> AsyncGenerator[ProviderEvent, None]:
    """Stream from the provider, retrying transient failures before any output.

    A retry re-issues the same request inside the same attempt; nothing is
    duplicated because retries are only allowed while the buffer is empty. Each
    attempt is bounded by ``first_token_timeout`` until the first text arrives,
    so a queued provider fails with a retryable timeout instead of a blank wait.
    """
    retry_index = 0
    emitted = False

    while True:
        try:
            deadline = None if emitted else loop.first_token_timeout
            async for event in _bounded_stream(provider, request, deadline=deadline):
                if isinstance(event, TextDelta):
                    emitted = True
                yield event
                if isinstance(event, StreamCompleted):
                    # The provider may keep its stream open after the terminal
                    # event; stop here instead of waiting for it to end.
                    return
            return
        except FirstTokenTimeout:
            # Never auto-retried: the provider is queued, so retrying only
            # multiplies the wait. The user still gets a retry action.
            raise
        except ProviderError as error:
            if not _should_retry(error, emitted=emitted, retry_index=retry_index, loop=loop):
                raise

            delay = loop.policy.delay_seconds(retry_index)
            logger.warning(
                "retrying provider call",
                extra={
                    "ctx_attempt_id": str(loop.attempt_id),
                    "ctx_retry_index": retry_index + 1,
                    "ctx_delay_seconds": round(delay, 3),
                    "ctx_error_code": error.code,
                },
            )
            retry_index += 1
            loop.telemetry.mark_retry()
            if await _sleep_or_stop(loop.stop_event, delay):
                return


def _should_retry(
    error: ProviderError,
    *,
    emitted: bool,
    retry_index: int,
    loop: RetryLoop,
) -> bool:
    """A hint of several seconds means retrying now would only extend the limit."""
    if isinstance(error, ProviderRateLimited) and (error.retry_after_seconds or 0) > 2.0:
        return False
    if not loop.policy.is_retryable(error, has_output=emitted):
        return False
    return retry_index < loop.policy.max_retries


class _EndOfStream:
    """Queue sentinel marking a normally finished provider stream."""


_END_OF_STREAM = _EndOfStream()


async def _bounded_stream(
    provider: ChatProvider,
    request: GenerationRequest,
    *,
    deadline: float | None,
) -> AsyncGenerator[ProviderEvent, None]:
    """Yield provider events, enforcing a hard deadline on the first event.

    The provider runs in its own task so the deadline holds even when the SDK
    ignores cancellation while retrying internally. That was observed as a
    seven-minute wait that outlived ``asyncio.timeout``.
    """
    queue: asyncio.Queue[ProviderEvent | BaseException | _EndOfStream] = asyncio.Queue()
    producer = asyncio.create_task(_pump_stream(provider, request, queue))
    emitted = False

    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=None if emitted else deadline)
            except TimeoutError as error:
                raise FirstTokenTimeout(detail=f"no provider event within {deadline}s") from error

            if isinstance(item, _EndOfStream):
                return
            if isinstance(item, BaseException):
                raise item
            emitted = True
            yield item
    finally:
        if not producer.done():
            # Do not await: a stuck SDK call must not block the response.
            producer.cancel()
            producer.add_done_callback(_discard_task_result)


async def _pump_stream(
    provider: ChatProvider,
    request: GenerationRequest,
    queue: asyncio.Queue[ProviderEvent | BaseException | _EndOfStream],
) -> None:
    """Forward provider events into a queue so the consumer can time out."""
    try:
        async for event in provider.stream(request):
            queue.put_nowait(event)
        queue.put_nowait(_END_OF_STREAM)
    except asyncio.CancelledError:
        raise
    except Exception as error:
        queue.put_nowait(error)


def _discard_task_result(task: asyncio.Task[object]) -> None:
    with suppress(asyncio.CancelledError, Exception):
        task.exception()


async def _sleep_or_stop(stop_event: asyncio.Event, delay: float) -> bool:
    """Sleep unless a stop is requested first. Returns True when stopped."""
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=delay)
    except TimeoutError:
        return False
    return True
