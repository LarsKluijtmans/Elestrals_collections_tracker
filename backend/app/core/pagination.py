"""Opaque cursors.

`api-conventions.md` mandates cursor pagination, not offset — `OFFSET 9000` degrades exactly
where the 10,000-row target lives. The cursor is opaque on the wire so the encoding can change
without breaking a client that stored one.

For result sets with a **total order** (catalog search, checklists, import runs) the cursor
currently encodes an offset. That is sound precisely because the order is total: the same query
returns the same sequence, so page 2 cannot skip or repeat a row. When a query without a total
order needs paging, it needs a keyset cursor instead — and this is the one place to add it.
"""
from __future__ import annotations

import base64
import binascii


def encode_cursor(raw: str) -> str:
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str | None) -> str | None:
    """Returns None for an absent cursor; raises `ValueError` for a malformed one."""
    if not cursor:
        return None
    try:
        return base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise ValueError("malformed cursor") from exc


def decode_offset(cursor: str | None) -> int:
    raw = decode_cursor(cursor)
    if raw is None:
        return 0
    if not raw.isdigit():
        raise ValueError("malformed cursor")
    return int(raw)


def next_offset_cursor(*, offset: int, page_size: int, has_more: bool) -> str | None:
    return encode_cursor(str(offset + page_size)) if has_more else None
