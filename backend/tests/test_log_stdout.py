"""Errors and startup events reach stdout — the operator channel this service did not have.

Found by the first real deploy of the full stack, 2026-08-17. The M2M scope check fired correctly,
logged an `error`, and wrote it to `app_logs`, where nobody looked: `docker compose logs
elestrals-api` showed uvicorn access lines and nothing else, and the platform forward was dead
because the very scope it needed (`logs:write`) was the missing one.

So a check whose own docstring says *"we check once, at startup, and shout"* was whispering into a
table that needs a MySQL client to read. These tests pin the fix.
"""
from __future__ import annotations

import json

import pytest

from app.services.logging_service import log_event


def emitted(caplog) -> list[dict]:
    """Every JSON object this module logged, parsed.

    Read through `caplog` rather than `capsys`, and the reason is worth knowing: the handler binds
    `sys.stdout` when the module is imported, which is correct in a container — the stream never
    changes — but pytest replaces `sys.stdout` *after* the import, so `capsys` never sees it.
    Asserting on the records tests the same thing without fighting the fixture.

    `test_the_handler_writes_to_stdout` covers the half this cannot: that the stream really is
    stdout, which is the whole operator-visibility claim.
    """
    out = []
    for record in caplog.records:
        if record.name != "elestrals":
            continue
        try:
            out.append(json.loads(record.getMessage()))
        except json.JSONDecodeError:
            continue
    return out


def test_an_error_reaches_stdout(db, caplog):
    """**The one the deploy was missing.** An error nobody can see is an error nobody fixes."""
    log_event("error", "something went wrong", component="scope-check", operation="startup")

    events = emitted(caplog)
    assert any(e["message"] == "something went wrong" and e["level"] == "error" for e in events)


def test_a_critical_reaches_stdout(db, caplog):
    log_event("critical", "the roof is on fire", component="whatever")
    assert any(e["level"] == "critical" for e in emitted(caplog))


def test_startup_events_reach_stdout_at_any_level(db, caplog):
    """Lifecycle is the other thing an operator greps for after a deploy — and "starting" is an
    `info`, so a level filter alone would drop it."""
    log_event("info", "starting", component="lifecycle", operation="startup")
    assert any(e["message"] == "starting" for e in emitted(caplog))


def test_the_scope_check_warning_reaches_stdout(db, caplog):
    """The exact case from the deploy: `component="startup"`, and a `warning` rather than an
    error when credentials are absent entirely."""
    log_event("warning", "M2M credentials not configured", component="startup",
              operation="scope-check")
    assert any("M2M credentials" in e["message"] for e in emitted(caplog))


def test_routine_logs_stay_off_stdout(db, caplog):
    """Deliberately not everything. Request logs on stdout would bury the two lines that matter,
    and they are already in `app_logs` where they can be joined against domain tables."""
    log_event("info", "GET /api/v1/health", component="http", operation="request")

    assert not any(e.get("message") == "GET /api/v1/health" for e in emitted(caplog))


def test_stdout_is_one_json_object_per_line(db, caplog):
    """The shape a container runtime collects, and the same one `harvest-api` emits — so both
    services can be parsed by one thing rather than two."""
    log_event("error", "boom", component="x", operation="y", context={"k": "v"})

    (event,) = [e for e in emitted(caplog) if e.get("message") == "boom"]
    assert set(event) >= {"level", "message", "component", "operation", "category", "service"}
    assert event["context"] == {"k": "v"}


def test_stdout_carries_redacted_values_only(db, caplog):
    """Container logs are collected and shipped like anything else, so an unredacted message on
    stdout would defeat the redaction entirely."""
    log_event("error", "failed", component="x", context={"password": "hunter2"})

    (event,) = [e for e in emitted(caplog) if e.get("message") == "failed"]
    assert "hunter2" not in json.dumps(event)


def test_an_error_reaches_stdout_even_when_the_database_write_fails(db, caplog, monkeypatch):
    """**The case that matters most.** MySQL being unreachable is exactly when `app_logs` cannot
    record the error, and exactly when somebody is reading `docker compose logs` to find out why.
    So stdout is written first, outside the database write."""
    import app.services.logging_service as svc

    def explode(*args, **kwargs):
        raise RuntimeError("database is gone")

    monkeypatch.setattr(svc, "SessionLocal", explode)
    log_event("error", "database is unreachable", component="db")

    assert any(e.get("message") == "database is unreachable" for e in emitted(caplog))


def test_logging_never_raises(db, monkeypatch):
    """The rule the whole module is built on, extended to the new destination: a broken stdout
    must not take down the request it was describing."""
    import app.services.logging_service as svc

    monkeypatch.setattr(svc._stdout, "log", lambda *a, **k: (_ for _ in ()).throw(OSError("pipe")))
    log_event("error", "still fine", component="x")  # must not raise


@pytest.mark.parametrize("level", ["debug", "info", "warning"])
def test_ordinary_levels_do_not_reach_stdout(db, caplog, level):
    log_event(level, f"routine {level}", component="http")
    assert not any(e.get("message") == f"routine {level}" for e in emitted(caplog))


def test_the_handler_writes_to_stdout():
    """The operator-visibility claim itself: **stdout**, not stderr.

    `docker compose logs` shows both, but they interleave differently and a structured log stream
    split across two file descriptors is one nobody can pipe into anything. `harvest-api` chose
    stdout; this matches it, so both services parse as one stream.
    """
    import sys

    import app.services.logging_service as svc

    streams = [h.stream for h in svc._stdout.handlers if hasattr(h, "stream")]
    assert sys.stdout in streams or any(getattr(s, "name", None) == "<stdout>" for s in streams)
