"""Redaction is the security-critical piece of the logging path: it runs before persistence,
so a miss is a credential written to disk."""
from __future__ import annotations

from app.core.redaction import REDACTED, redact, scrub_text, strip_query_string


def test_sensitive_keys_are_redacted():
    out = redact({
        "authorization": "Bearer abc.def.ghi",
        "client_secret": "s3cr3t",
        "password": "hunter2",
        "refresh_token": "rt-123",
        "printing_id": "keep-me",
    })
    assert out["authorization"] == REDACTED
    assert out["client_secret"] == REDACTED
    assert out["password"] == REDACTED
    assert out["refresh_token"] == REDACTED
    assert out["printing_id"] == "keep-me"


def test_nested_structures_are_redacted():
    out = redact({"outer": {"list": [{"api_key": "k"}, {"ok": 1}]}})
    assert out["outer"]["list"][0]["api_key"] == REDACTED
    assert out["outer"]["list"][1]["ok"] == 1


def test_bearer_and_jwt_inside_free_text():
    assert REDACTED in scrub_text("failed with Bearer eyJhbGciOiJSUzI1NiJ9.payload.sig")
    assert REDACTED in scrub_text("token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9abcdefghij")


def test_validation_error_payload_is_redacted():
    """FastAPI echoes the offending input back. A malformed body carrying a secret must not
    reach the log store verbatim — this is the case the platform standards call out."""
    errors = [{"loc": ["body", "client_secret"], "msg": "field required", "input": "s3cr3t"}]
    out = redact(errors)
    assert out[0]["input"] == REDACTED


def test_query_strings_are_never_logged():
    assert strip_query_string("/api/v1/inventory?token=abc&set=BASE") == "/api/v1/inventory"


def test_redaction_never_raises():
    class Hostile:
        def __repr__(self):  # noqa: D105
            raise RuntimeError("boom")

    assert redact({"x": Hostile()}) is not None


def test_depth_is_bounded():
    deep: dict = {}
    node = deep
    for _ in range(50):
        node["n"] = {}
        node = node["n"]
    assert redact(deep) is not None
