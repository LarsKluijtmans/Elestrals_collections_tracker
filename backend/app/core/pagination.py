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


# --- keyset cursors ------------------------------------------------------------------
#
# The case this module's docstring reserved. The collection table pages over a *mutable* result
# set — a collector is adding rows while scrolling — so an offset cursor does the thing offsets
# do: insert a row above the window and page 2 repeats a row; delete one and page 2 skips one.
# Neither is visible as an error. Both are visible as "the table is missing a card", which is
# the single worst bug this product can have.
#
# A keyset cursor names the last row seen instead of counting past it, so the next page is
# "everything after *this* row" and inserts and deletes elsewhere cannot shift it.


def encode_keyset(*parts: str) -> str:
    """Encode the sort key of the last row on a page.

    Parts are joined with `\\x1f` (ASCII unit separator) rather than a comma or a pipe: the parts
    are timestamps and UUIDs today, but a future sort key could be a card name, and a name
    containing the delimiter would split into the wrong number of fields and be rejected as
    malformed. `\\x1f` cannot appear in any of them.
    """
    return encode_cursor("\x1f".join(parts))


def decode_keyset(cursor: str | None, *, arity: int) -> tuple[str, ...] | None:
    """Decode a keyset cursor, or None if absent. Raises `ValueError` if malformed.

    `arity` is checked rather than assumed. A cursor minted by an older deploy with a different
    sort key would otherwise unpack into the wrong columns and silently return the wrong page —
    a stale cursor must fail loudly and send the client back to page 1.
    """
    raw = decode_cursor(cursor)
    if raw is None:
        return None
    parts = tuple(raw.split("\x1f"))
    if len(parts) != arity:
        raise ValueError("malformed cursor")
    return parts
