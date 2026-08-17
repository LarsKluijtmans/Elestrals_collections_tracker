"""`log_event()` — the ONLY way anything in this application writes a log.

Three destinations, one call site:

  * `elestrals.app_logs`  — everything, debug through critical. Joinable against our own
    domain tables, which is why it exists alongside the platform's store.
  * **stdout**            — `error`, `critical`, and anything at startup, as structured JSON.
  * logs-api              — `error`, `critical`, and every `security`-category entry, so an
    outage here is visible in the platform console where the operator is actually looking.

**Why stdout was added on 2026-08-17.** The first real deploy of the full stack found that this
service had *no operator-visible error channel at all*. The M2M scope check fired correctly, logged
an `error`, and wrote it to `app_logs` — where nobody looked. `docker compose logs elestrals-api`
showed uvicorn access lines and nothing else, and the platform forward was dead because the very
scope it needed (`logs:write`) was the one missing.

A check whose docstring says *"we check once, at startup, and shout"* was whispering into a table
that requires a MySQL client to read. `harvest-api` had this right from the start — structured JSON
to stdout, collected by the container runtime — and this now matches it.

Deliberately **not** everything: routine request logs on stdout would bury the two lines that
matter, and they are already in `app_logs`. Errors and startup only.

Call sites never choose a destination. The routing rule lives in this function alone, so it
can be changed once rather than re-decided at every log statement. Direct writes to
`app_logs`, and direct `logs.write` calls, are a review failure.

Forwarding runs on a daemon thread behind a **bounded** queue: a logs-api outage must delay
forwarding, never grow memory without end, and never — under any circumstance — fail the
request being described.
"""
from __future__ import annotations

import atexit
import json
import logging
import queue
import sys
import threading
import traceback
from typing import Any

from ..config import settings
from ..core.db import SessionLocal
from ..core.redaction import redact
from ..models.app_log import LEVELS, AppLog
from ..project_logger import forward_to_platform
from ..repositories.app_log_repository import AppLogRepository

_FORWARD_LEVELS = ("error", "critical")
_FORWARD_CATEGORIES = ("security",)

#: What reaches stdout. Errors, and anything from the lifecycle — the two things an operator
#: greps for after a deploy, and the two things `app_logs` alone cannot tell them.
_STDOUT_LEVELS = ("error", "critical")
_STDOUT_COMPONENTS = ("startup", "lifecycle")

_stdout = logging.getLogger("elestrals")
if not _stdout.handlers:  # pragma: no cover - configured once per process
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _stdout.addHandler(_handler)
    _stdout.setLevel(logging.INFO)

_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=settings.log_forward_buffer_max)
_dropped = 0
_dropped_lock = threading.Lock()


def _worker() -> None:
    while True:
        event = _queue.get()
        if event is None:  # shutdown sentinel
            return
        try:
            forward_to_platform(event)
        except Exception:
            # Swallow: a forwarding failure is not an application failure.
            pass
        finally:
            _queue.task_done()


_thread = threading.Thread(target=_worker, name="log-forwarder", daemon=True)
_thread.start()


@atexit.register
def _drain() -> None:
    try:
        _queue.put_nowait(None)  # type: ignore[arg-type]
    except queue.Full:
        pass


def dropped_forward_count() -> int:
    """Exposed so the drop count is observable rather than silent."""
    with _dropped_lock:
        return _dropped


def _should_forward(level: str, category: str) -> bool:
    return level in _FORWARD_LEVELS or category in _FORWARD_CATEGORIES


def log_event(
    level: str,
    message: str,
    *,
    category: str | None = None,
    component: str | None = None,
    operation: str | None = None,
    user_sub: str | None = None,
    request_id: str | None = None,
    status_code: int | None = None,
    duration_ms: int | None = None,
    context: dict[str, Any] | None = None,
    exc: BaseException | None = None,
) -> None:
    """Write one event. Never raises."""
    global _dropped
    try:
        level = level if level in LEVELS else "info"
        category = category or settings.log_category
        trace = None
        if exc is not None:
            trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        elif level in ("error", "critical"):
            trace = "".join(traceback.format_stack())

        # Redact BEFORE persistence — including anything echoed back from a validation error.
        safe_context = redact(context) if context else None
        forward = _should_forward(level, category)

        entry = AppLog(
            level=level,
            category=category,
            component=component,
            operation=operation,
            message=redact(message) if isinstance(message, str) else str(message),
            user_sub=user_sub,
            request_id=request_id,
            status_code=status_code,
            duration_ms=duration_ms,
            context=safe_context,
            trace=trace,
            forwarded_to_platform=forward and settings.enable_project_logging,
        )

        # stdout FIRST, and outside the database write. An error raised because MySQL is
        # unreachable is exactly when `app_logs` cannot record it, and exactly when somebody is
        # reading `docker compose logs` to find out why.
        if level in _STDOUT_LEVELS or component in _STDOUT_COMPONENTS:
            _to_stdout(level, entry_message=redact(message) if isinstance(message, str)
                       else str(message),
                       category=category, component=component, operation=operation,
                       context=safe_context)

        # Own session: a log write must not ride on — or roll back with — the request's
        # transaction. An error logged inside a failing request still has to survive.
        db = SessionLocal()
        try:
            AppLogRepository(db).add(entry)
        finally:
            db.close()

        if forward and settings.enable_project_logging:
            payload = {
                "level": level,
                "category": category,
                "message": entry.message,
                "metadata": {
                    "component": component,
                    "operation": operation,
                    "request_id": request_id,
                    "status_code": status_code,
                    **(safe_context or {}),
                },
            }
            try:
                _queue.put_nowait(payload)
            except queue.Full:
                # Bounded on purpose. Drop, count, and keep serving — app_logs still has it.
                with _dropped_lock:
                    _dropped += 1
    except Exception:
        # A logging failure must never surface to the user, and must never mask the
        # original error being logged.
        pass


def _to_stdout(
    level: str,
    *,
    entry_message: str,
    category: str | None,
    component: str | None,
    operation: str | None,
    context: dict[str, Any] | None,
) -> None:
    """One JSON object per line, the same shape `harvest-api` emits.

    Already-redacted values only — this is called after `redact`, and putting an unredacted
    message on stdout would defeat the redaction entirely, since container logs are collected and
    shipped like any other.
    """
    try:
        _stdout.log(
            _STDOUT_LEVELS.index(level) * 10 + 40 if level in _STDOUT_LEVELS else 20,
            json.dumps({
                "level": level,
                "message": entry_message,
                "component": component,
                "operation": operation,
                "category": category,
                "service": settings.app_name,
                **({"context": context} if context else {}),
            }, default=str),
        )
    except Exception:
        # Same rule as everywhere in this module: a logging failure is never an application
        # failure. A broken stdout must not take down the request it was describing.
        pass
