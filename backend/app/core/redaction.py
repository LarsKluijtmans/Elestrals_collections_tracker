"""Strip secrets from log context BEFORE persistence.

Two rules from the platform's standards, both non-negotiable:

  * Never log authorization headers, passwords, tokens, API keys, secrets, or any value
    matching a sensitive key pattern.
  * Query strings are never logged.

This runs before the row is written, not before it is displayed. A redact-on-read design
leaks the moment someone queries the table directly, or takes a database dump.

The `RequestValidationError` path matters especially: FastAPI echoes the offending input
back, so a malformed request body containing a secret would otherwise land in the log store
verbatim.
"""
from __future__ import annotations

import re
from typing import Any

REDACTED = "[redacted]"

# Substring match on the lowercased key — deliberately broad. A false positive costs one
# unreadable log field; a false negative persists a credential.
_SENSITIVE_KEY_PARTS = (
    "authorization", "auth", "password", "passwd", "secret", "token", "api_key", "apikey",
    "client_secret", "credential", "cookie", "session", "private", "signature", "otp",
    "code_verifier", "refresh",
)

# Bearer tokens and long base64ish blobs appearing inside free text.
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]+")
_JWTISH = re.compile(r"\beyJ[A-Za-z0-9._\-]{20,}")

_MAX_DEPTH = 6
_MAX_STR = 2048


def _is_sensitive(key: str) -> bool:
    k = key.lower()
    return any(part in k for part in _SENSITIVE_KEY_PARTS)


def scrub_text(value: str) -> str:
    value = _BEARER.sub(f"Bearer {REDACTED}", value)
    value = _JWTISH.sub(REDACTED, value)
    if len(value) > _MAX_STR:
        value = value[:_MAX_STR] + "…[truncated]"
    return value


# Pydantic/FastAPI validation errors carry the offending value under a neutral key
# (`input`), while the sensitive *name* lives inside `loc`. Key-name matching alone misses
# this entirely, which is precisely how a submitted secret reaches the log store.
_ECHO_KEYS = ("input", "value", "ctx")


def _loc_is_sensitive(value: Any) -> bool:
    loc = value.get("loc") if isinstance(value, dict) else None
    if not isinstance(loc, (list, tuple)):
        return False
    return any(_is_sensitive(str(part)) for part in loc)


def redact(value: Any, _depth: int = 0) -> Any:
    """Recursively redact a log-context value. Never raises — a redaction failure must not
    become a logging failure, and a logging failure must not become a request failure."""
    if _depth > _MAX_DEPTH:
        return "[max-depth]"
    try:
        if isinstance(value, dict):
            echo_sensitive = _loc_is_sensitive(value)
            return {
                k: (
                    REDACTED
                    if _is_sensitive(str(k)) or (echo_sensitive and str(k) in _ECHO_KEYS)
                    else redact(v, _depth + 1)
                )
                for k, v in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [redact(v, _depth + 1) for v in value]
        if isinstance(value, str):
            return scrub_text(value)
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        return scrub_text(str(value))
    except Exception:
        return "[unredactable]"


def strip_query_string(path: str) -> str:
    """Log the path, never the query string."""
    return path.split("?", 1)[0]
