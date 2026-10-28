"""Cursor encoding and validation."""

import base64
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from chatbot.application.cursor import Cursor, CursorError, decode_cursor, encode_cursor


def _cursor() -> Cursor:
    return Cursor(
        updated_at=datetime(2026, 10, 28, 18, 4, 2, 918000, tzinfo=UTC),
        id=uuid.UUID(int=0x0123_4567_89AB_CDEF_0123_4567_89AB_CDEF),
    )


def test_round_trip_preserves_position() -> None:
    original = _cursor()

    decoded = decode_cursor(encode_cursor(original))

    assert decoded == original


def test_cursor_is_url_safe_without_padding() -> None:
    token = encode_cursor(_cursor())

    assert "=" not in token
    assert "+" not in token
    assert "/" not in token


def test_empty_cursor_is_rejected() -> None:
    with pytest.raises(CursorError):
        decode_cursor("")


def test_malformed_base64_is_rejected() -> None:
    with pytest.raises(CursorError):
        decode_cursor("!!!not-base64!!!")


def test_non_json_payload_is_rejected() -> None:
    token = base64.urlsafe_b64encode(b"not json").decode().rstrip("=")

    with pytest.raises(CursorError):
        decode_cursor(token)


def test_missing_fields_are_rejected() -> None:
    token = base64.urlsafe_b64encode(json.dumps({"u": "2026-10-28T18:04:02+00:00"}).encode())
    token = token.decode().rstrip("=")

    with pytest.raises(CursorError):
        decode_cursor(token)


def test_naive_timestamp_is_rejected() -> None:
    payload = {"u": "2026-10-28T18:04:02", "i": str(uuid.UUID(int=1))}
    token = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")

    with pytest.raises(CursorError):
        decode_cursor(token)


def test_invalid_uuid_is_rejected() -> None:
    payload = {"u": "2026-10-28T18:04:02+00:00", "i": "not-a-uuid"}
    token = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")

    with pytest.raises(CursorError):
        decode_cursor(token)


def test_cursor_ordering_comparison_is_stable() -> None:
    first = _cursor()
    second = Cursor(updated_at=first.updated_at - timedelta(seconds=1), id=first.id)

    assert second.updated_at < first.updated_at
