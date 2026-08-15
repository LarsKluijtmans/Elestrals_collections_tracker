"""The routing rule — which entries reach the platform — lives in exactly one function.
These tests pin it there, so a future call site cannot quietly acquire its own policy."""
from __future__ import annotations

from app.services.logging_service import _should_forward


def test_errors_and_criticals_forward():
    assert _should_forward("error", "inventory")
    assert _should_forward("critical", "http")


def test_security_category_forwards_at_any_level():
    # A 401 is logged at warning, but it is a security event and must reach the console.
    assert _should_forward("warning", "security")
    assert _should_forward("info", "security")


def test_routine_entries_stay_local():
    assert not _should_forward("info", "http")
    assert not _should_forward("debug", "inventory")
    assert not _should_forward("warning", "catalog")
