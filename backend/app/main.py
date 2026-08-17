"""FastAPI entrypoint.

Run it from `backend/`:
    uvicorn app.main:app --host 127.0.0.1 --port 9000 --reload
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import settings
from .controllers import (
    account, admin_catalog, alerts, catalog, collection, events, health, import_export,
    inventory, me, prices, sealed_and_wishlist,
)
from .core.redaction import redact
from .core.scope_check import assert_m2m_scopes
from .middleware.request_logging import RequestLoggingMiddleware
from .services.logging_service import log_event


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_event("info", "starting", component="lifecycle", operation="startup",
              context={"environment": settings.environment})
    # A missing M2M scope otherwise surfaces much later as a silent 403 inside a call that
    # swallows errors by design. Fail loudly here instead — outside production, where a
    # startup abort would be worse than a degraded feature.
    assert_m2m_scopes(fail_fast=not settings.is_production)
    yield
    log_event("info", "shutting down", component="lifecycle", operation="shutdown")


app = FastAPI(
    title="Elestral Vault backend",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,  # Bearer tokens, not cookies
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    """FastAPI echoes the offending input back. Redact it before it reaches a log store or
    the client — a malformed body carrying a secret must not leak either way."""
    safe = redact([{"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")}
                   for e in exc.errors()])
    log_event("warning", "request validation failed", component="http", operation="validate",
              request_id=getattr(request.state, "request_id", None),
              status_code=422, context={"errors": safe})
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error",
                           "message": "Request validation failed",
                           "details": {"errors": safe}}},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Normalise every HTTPException onto the platform error shape."""
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        body = exc.detail
    else:
        body = {"error": {"code": _default_code(exc.status_code),
                          "message": str(exc.detail), "details": {}}}
    return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)


def _default_code(status_code: int) -> str:
    return {
        400: "bad_request", 401: "unauthorized", 403: "forbidden",
        404: "not_found", 409: "conflict", 429: "rate_limited",
    }.get(status_code, "error")


app.include_router(health.router)
app.include_router(me.router)
app.include_router(events.router)
app.include_router(catalog.router)
app.include_router(inventory.router)
app.include_router(collection.router)
app.include_router(sealed_and_wishlist.router)
app.include_router(import_export.router)
app.include_router(account.router)
app.include_router(alerts.router)
app.include_router(prices.router)
app.include_router(admin_catalog.router)
