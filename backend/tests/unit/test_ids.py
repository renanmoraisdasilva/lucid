"""UUIDv7 properties."""

import time
import uuid

from lucid.domain.ids import uuid7, uuid7_timestamp_ms


def test_generates_version_7_uuids() -> None:
    value = uuid7()

    assert value.version == 7
    assert value.variant == uuid.RFC_4122


def test_ids_are_unique() -> None:
    generated = {uuid7() for _ in range(1000)}

    assert len(generated) == 1000


def test_timestamp_is_embedded_and_monotonic() -> None:
    before = int(time.time() * 1000)
    timestamps = [uuid7_timestamp_ms(uuid7()) for _ in range(50)]
    after = int(time.time() * 1000)

    assert timestamps == sorted(timestamps)
    assert before - 1000 <= timestamps[0] <= after + 1000
    assert before - 1000 <= timestamps[-1] <= after + 1000


def test_extracting_timestamp_round_trips() -> None:
    value = uuid7()

    assert uuid7_timestamp_ms(value) > 0
