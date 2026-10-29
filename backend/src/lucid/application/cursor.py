"""Opaque keyset pagination cursors over (updated_at, id)."""

import base64
import binascii
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import cast


class CursorError(ValueError):
    """Raised when a cursor cannot be decoded."""


@dataclass(frozen=True, slots=True)
class Cursor:
    """Position in a conversation list ordered by updated_at DESC, id DESC."""

    updated_at: datetime
    id: uuid.UUID


def encode_cursor(cursor: Cursor) -> str:
    """Serialize a cursor as an opaque URL-safe token."""
    payload = json.dumps(
        {"u": cursor.updated_at.isoformat(), "i": str(cursor.id)},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_cursor(token: str) -> Cursor:
    """Parse a cursor token, raising CursorError when it is not one of ours."""
    if not token:
        raise CursorError("Cursor is empty")
    padding = "=" * (-len(token) % 4)
    try:
        raw = base64.urlsafe_b64decode(token + padding)
        decoded = json.loads(raw)
    except (binascii.Error, ValueError, UnicodeDecodeError) as error:
        raise CursorError("Cursor is not valid base64 or JSON") from error

    if not isinstance(decoded, dict):
        raise CursorError("Cursor payload is not an object")
    payload = cast("dict[str, object]", decoded)
    updated_at_raw = payload.get("u")
    id_raw = payload.get("i")
    if not isinstance(updated_at_raw, str) or not isinstance(id_raw, str):
        raise CursorError("Cursor payload is missing fields")

    try:
        updated_at = datetime.fromisoformat(updated_at_raw)
        identifier = uuid.UUID(id_raw)
    except ValueError as error:
        raise CursorError("Cursor payload has invalid values") from error

    if updated_at.tzinfo is None:
        raise CursorError("Cursor timestamp must be timezone-aware")

    return Cursor(updated_at=updated_at, id=identifier)
