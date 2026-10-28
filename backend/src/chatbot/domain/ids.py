"""UUIDv7 generation.

Time-ordered UUIDs keep B-tree inserts local and give us a sortable primary key
without leaking row counts. The standard library has no v7 support (as of Python
3.12), and the dependency is not worth adding for twenty lines.

Layout (RFC 9562, version 7):
  bits  0..47   unix timestamp, milliseconds, big-endian
  bits 48..51   version (0111)
  bits 52..63   rand_a
  bits 64..65   variant (10)
  bits 66..127  rand_b
"""

import os
import time
import uuid

_UNIX_TS_MASK = (1 << 48) - 1
_RAND_A_BITS = 12
_RAND_B_BITS = 62


def uuid7() -> uuid.UUID:
    """Return a new UUIDv7 based on the current time and 74 random bits."""
    timestamp_ms = (time.time_ns() // 1_000_000) & _UNIX_TS_MASK
    rand_a = int.from_bytes(os.urandom(2), "big") & ((1 << _RAND_A_BITS) - 1)
    rand_b = int.from_bytes(os.urandom(8), "big") & ((1 << _RAND_B_BITS) - 1)

    value = timestamp_ms << 80
    value |= 0x7 << 76
    value |= rand_a << 64
    value |= 0b10 << 62
    value |= rand_b
    return uuid.UUID(int=value)


def uuid7_timestamp_ms(value: uuid.UUID) -> int:
    """Extract the millisecond timestamp embedded in a UUIDv7."""
    return value.int >> 80
