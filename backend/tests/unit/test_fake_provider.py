"""Fake provider behaviour used by the application tests."""

import pytest

from lucid.domain.enums import Role
from lucid.domain.errors import ProviderRateLimited
from lucid.domain.provider import (
    ChatProvider,
    GenerationRequest,
    ProviderMessage,
    StreamCompleted,
    TextDelta,
)
from lucid.providers.fake import FakeProvider, FakeScript


def _request() -> GenerationRequest:
    return GenerationRequest(
        model="fake-model",
        system_prompt="be brief",
        messages=[ProviderMessage(role=Role.USER, content="hello")],
        max_output_tokens=64,
        request_id="req-1",
    )


async def _collect(provider: FakeProvider, request: GenerationRequest) -> list[object]:
    return [event async for event in provider.stream(request)]


def test_fake_provider_satisfies_the_protocol() -> None:
    assert isinstance(FakeProvider(), ChatProvider)


async def test_streams_text_then_completion_with_usage() -> None:
    events = await _collect(FakeProvider(), _request())

    deltas = [event for event in events if isinstance(event, TextDelta)]
    assert [delta.text for delta in deltas] == ["Fake ", "response", "."]
    assert isinstance(events[-1], StreamCompleted)
    assert events[-1].usage is not None
    assert events[-1].usage.total_tokens == 18


async def test_records_the_requests_it_received() -> None:
    provider = FakeProvider()

    await _collect(provider, _request())

    assert len(provider.requests) == 1
    assert provider.requests[0].request_id == "req-1"


async def test_can_fail_before_the_first_token() -> None:
    provider = FakeProvider(FakeScript(fail_before_first_token=ProviderRateLimited()))

    with pytest.raises(ProviderRateLimited):
        await _collect(provider, _request())


async def test_can_fail_after_the_first_token() -> None:
    provider = FakeProvider(
        FakeScript(
            deltas=("partial ", "rest"),
            fail_after_first_token=ProviderRateLimited(detail="boom"),
        )
    )

    received: list[object] = []
    with pytest.raises(ProviderRateLimited):
        async for event in provider.stream(_request()):
            received.append(event)

    assert [event.text for event in received if isinstance(event, TextDelta)] == ["partial "]


async def test_can_report_missing_usage() -> None:
    provider = FakeProvider(FakeScript(deltas=("x",), usage=None))

    events = await _collect(provider, _request())

    completion = events[-1]
    assert isinstance(completion, StreamCompleted)
    assert completion.usage is None


async def test_script_can_be_replaced_between_calls() -> None:
    provider = FakeProvider()
    await _collect(provider, _request())

    provider.set_script(FakeScript(deltas=("changed",)))

    events = await _collect(provider, _request())
    deltas = [event.text for event in events if isinstance(event, TextDelta)]
    assert deltas == ["changed"]
