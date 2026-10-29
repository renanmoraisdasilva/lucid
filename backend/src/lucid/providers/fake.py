"""Deterministic fake provider for tests and offline development."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from lucid.domain.provider import (
    GenerationRequest,
    ProviderEvent,
    StreamCompleted,
    TextDelta,
    Usage,
)


def _default_usage() -> Usage:
    return Usage(input_tokens=11, output_tokens=7, thought_tokens=0, total_tokens=18)


@dataclass(slots=True)
class FakeScript:
    """How the fake provider should behave for one call."""

    deltas: tuple[str, ...] = ("Fake ", "response", ".")
    usage: Usage | None = field(default_factory=_default_usage)
    fail_before_first_token: Exception | None = None
    fail_after_first_token: Exception | None = None
    delay_seconds: float = 0.0


class FakeProvider:
    """Scripted provider: no network, no quota, deterministic timing."""

    name = "fake"

    def __init__(self, script: FakeScript | None = None) -> None:
        self.script = script or FakeScript()
        self.requests: list[GenerationRequest] = []

    def set_script(self, script: FakeScript) -> None:
        self.script = script

    async def stream(self, request: GenerationRequest) -> AsyncIterator[ProviderEvent]:
        self.requests.append(request)
        script = self.script

        if script.fail_before_first_token is not None:
            raise script.fail_before_first_token

        for index, delta in enumerate(script.deltas):
            if index == 1 and script.fail_after_first_token is not None:
                raise script.fail_after_first_token
            if script.delay_seconds:
                await asyncio.sleep(script.delay_seconds)
            yield TextDelta(text=delta)

        yield StreamCompleted(usage=script.usage)
