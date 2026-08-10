"""One `app_logs` row per request, plus capture of anything that escapes a handler.

Installed before any feature so that everything built after it is diagnosable. The path is
logged without its query string — query strings are never logged.
"""
from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ..core.redaction import strip_query_string
from ..services.logging_service import log_event

REQUEST_ID_HEADER = "X-Request-ID"


def _subject(request: Request) -> str | None:
    """The validated subject, if a dependency has already resolved one."""
    principal = getattr(request.state, "principal", None)
    return getattr(principal, "sub", None) if principal else None


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        path = strip_query_string(request.url.path)

        try:
            response: Response = await call_next(request)
        except Exception as exc:
            duration = int((time.perf_counter() - started) * 1000)
            log_event(
                "critical",
                f"unhandled exception on {request.method} {path}",
                component="http", operation=request.method.lower(),
                user_sub=_subject(request), request_id=request_id,
                status_code=500, duration_ms=duration,
                context={"path": path, "method": request.method},
                exc=exc,
            )
            # Standard error shape — never a bare detail string.
            return JSONResponse(
                status_code=500,
                content={"error": {"code": "internal_error",
                                   "message": "Internal server error",
                                   "details": {"request_id": request_id}}},
                headers={REQUEST_ID_HEADER: request_id},
            )

        duration = int((time.perf_counter() - started) * 1000)
        # 401/403 are security-category so they forward to the platform console; the
        # backend fixes category and severity, the browser cannot choose its own.
        if response.status_code in (401, 403):
            level, category = "warning", "security"
        elif response.status_code >= 500:
            level, category = "error", "http"
        else:
            level, category = "info", "http"

        log_event(
            level, f"{request.method} {path} -> {response.status_code}",
            category=category, component="http", operation=request.method.lower(),
            user_sub=_subject(request), request_id=request_id,
            status_code=response.status_code, duration_ms=duration,
            context={"path": path, "method": request.method},
        )
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
