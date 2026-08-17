"""FastAPI entrypoint for `harvest-api`, the second backend.

Run it from `harvest/`:
    uvicorn app.main:app --host 127.0.0.1 --port 9100 --reload

Every route under `/api/v1/admin` requires `elestrals:admin`. There are no other routes but
`/api/v1/health`, and that is the shape of the service: it exists to run scans and to be looked
at by an admin. Collectors never talk to it — they read `price_daily` through `elestrals-api`.
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
    admin_analysis, admin_listings, admin_maintenance, admin_runs, admin_sources, health,
)
from .services.logging_service import log_event


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_event(
        "info", "starting", component="lifecycle", operation="startup",
        context={"environment": settings.environment,
                 "obey_robots": settings.harvest_obey_robots,
                 "identified_as": settings.harvest_contact_email or "(unset)"},
    )
    # Two configuration mistakes that are silent until they matter, so they are said out loud
    # at startup instead.
    if not settings.harvest_contact_email.strip():
        log_event(
            "warning",
            "HARVEST_CONTACT_EMAIL is empty — no scan will start. ADR-004 gave up politeness, "
            "not identifiability.",
            component="lifecycle", operation="startup",
        )
    if settings.is_production and settings.harvest_admin_subs.strip():
        log_event(
            "warning",
            "HARVEST_ADMIN_SUBS is set in production and is being ignored. A subject allowlist "
            "is a development convenience, not an authorisation system.",
            component="lifecycle", operation="startup",
        )
    yield
    log_event("info", "shutting down", component="lifecycle", operation="shutdown")


app = FastAPI(
    title="Elestral Vault harvest",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,  # Bearer tokens, not cookies
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    safe = [{"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error",
                           "message": "Request validation failed",
                           "details": {"errors": safe}}},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Normalise every HTTPException onto the platform error shape — the same shape
    `elestrals-api` returns, so the SPA has one error contract rather than two."""
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        body = exc.detail
    else:
        body = {"error": {"code": _default_code(exc.status_code),
                          "message": str(exc.detail), "details": {}}}
    return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)


def _default_code(status_code: int) -> str:
    return {
        400: "bad_request", 401: "unauthorized", 403: "forbidden",
        404: "not_found", 409: "conflict", 422: "validation_error",
    }.get(status_code, "error")


app.include_router(health.router)
app.include_router(admin_sources.router)
app.include_router(admin_runs.router)
app.include_router(admin_listings.router)
app.include_router(admin_analysis.router)
app.include_router(admin_maintenance.router)
