"""`log_event()` — the ONLY way anything in this application writes a log.

Two destinations, one call site:

  * `elestrals.app_logs`  — everything, debug through critical. Joinable against our own
    domain tables, which is why it exists alongside the platform's store.
  * logs-api              — `error`, `critical`, and every `security`-category entry, so an
    outage here is visible in the platform console where the operator is actually looking.

Call sites never choose a destination. The routing rule lives in this function alone, so it
can be changed once rather than re-decided at every log statement. Direct writes to
`app_logs`, and direct `logs.write` calls, are a review failure.

Forwarding runs on a daemon thread behind a **bounded** queue: a logs-api outage must delay
forwarding, never grow memory without end, and never — under any circumstance — fail the
request being described.
"""
from __future__ import annotations

import atexit
import queue
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
