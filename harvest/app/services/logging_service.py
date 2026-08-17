"""`log_event()` — the only way anything in this service writes a log.

Phase 1's rule, kept: the routing decision lives in exactly one function so it can be changed
once. What is different here is the destination. `elestrals-api` writes to `app_logs` in the
`elestrals` schema; this service holds **no write grant** on that schema and is not going to be
given one for logging. So harvest logs go to stdout as structured JSON — which the container
runtime collects — and, when enabled, forward to logs-api like phase 1's do.

Best-effort throughout: a logging failure must never fail a scan. An exception here is swallowed
and counted, never propagated.
"""
from __future__ import annotations

import json
import logging
import sys
from typing import Any

import httpx

from ..config import settings

_logger = logging.getLogger("harvest")
if not _logger.handlers:  # pragma: no cover - configured once per process
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)

_LEVELS = {"debug": 10, "info": 20, "warning": 30, "error": 40, "critical": 50}

#: Counted rather than raised. A number that only goes up means the log path is broken, which
#: is worth knowing without it being able to break a scan.
forward_failures = 0


def log_event(
    level: str,
    message: str,
    *,
    component: str,
    operation: str,
    context: dict[str, Any] | None = None,
    exc: BaseException | None = None,
    run_id: str | None = None,
) -> None:
    """Emit one structured event. Never raises."""
    global forward_failures
    try:
        payload: dict[str, Any] = {
            "level": level,
            "message": message,
            "component": component,
            "operation": operation,
            "service": settings.app_name,
            "category": settings.log_category,
        }
        if run_id:
            payload["run_id"] = run_id
        if context:
            payload["context"] = context
        if exc is not None:
            payload["error"] = f"{type(exc).__name__}: {exc}"

        _logger.log(_LEVELS.get(level, 20), json.dumps(payload, default=str))

        # Only error and security-shaped entries are worth another service's storage — the same
        # rule phase 1 applies, so the two services do not flood logs-api differently.
        if settings.enable_project_logging and level in ("error", "critical"):
            _forward(payload)
    except Exception:  # noqa: BLE001 — logging must never fail the caller
        forward_failures += 1


def _forward(payload: dict[str, Any]) -> None:
    global forward_failures
    try:
        httpx.post(
            f"{settings.logs_api_url.rstrip('/')}/api/v1/logs",
            json=payload,
            timeout=3.0,
        )
    except Exception:  # noqa: BLE001 — an outage delays visibility, it does not stop a scan
        forward_failures += 1
