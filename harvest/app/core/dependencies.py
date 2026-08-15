"""DI wiring, and the admin gate.

`require_admin` is the single dependency every `/api/v1/admin/*` route on this service carries.
One dependency rather than a per-route check, because a per-route check is one a new route can
forget — and `tests/test_admin_auth.py` enumerates the router and asserts that none has.

The refusal is `403` with **no body detail**. A success-shaped response with the interesting
fields removed leaks the shape of what the caller cannot see, and teaches the frontend to render
an empty state that actually means "forbidden".
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..config import settings
from ..repositories.catalog_snapshot_repository import CatalogSnapshotRepository
from ..repositories.harvest_repository import HarvestRepository
from ..repositories.price_source_repository import PriceSourceRepository
from ..services.harvest_runner import HarvestRunner
from ..services.rollup_service import RollupService
from .db import get_db
from .security import Principal, verify_token


def current_principal(request: Request, principal: Principal = Depends(verify_token)) -> Principal:
    request.state.principal = principal
    return principal


def require_admin(principal: Principal = Depends(current_principal)) -> Principal:
    """The gate. Every admin route, no exceptions.

    `elestrals:operator` is deliberately **not** accepted. The person who can re-import the
    catalog is not automatically the person who can start a scraper against a site that has
    asked us not to — that separation is the reason there are two scopes.
    """
    scopes = principal.scope.split()
    if settings.admin_scope in scopes or principal.sub in settings.admin_subs_list:
        return principal
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"error": {"code": "forbidden", "message": "Admin access required",
                          "details": {}}},
    )


# --- repositories -------------------------------------------------------------------

def price_source_repository(db: Session = Depends(get_db)) -> PriceSourceRepository:
    return PriceSourceRepository(db)


def harvest_repository(db: Session = Depends(get_db)) -> HarvestRepository:
    return HarvestRepository(db)


def catalog_snapshot_repository(db: Session = Depends(get_db)) -> CatalogSnapshotRepository:
    return CatalogSnapshotRepository(db)


# --- services -----------------------------------------------------------------------

def make_harvest_runner(db: Session) -> HarvestRunner:
    """Compose a runner from a bare session.

    Used by the CLI and by the Celery task, so the scheduled path, the admin-triggered path and
    the command line are the same object graph rather than three wirings that drift. Story 017's
    "the trigger path and the scheduled path are the same code" is this function.
    """
    return HarvestRunner(
        sources=PriceSourceRepository(db),
        harvest=HarvestRepository(db),
        catalog=CatalogSnapshotRepository(db),
    )


def harvest_runner(db: Session = Depends(get_db)) -> HarvestRunner:
    return make_harvest_runner(db)


def make_rollup_service(db: Session) -> RollupService:
    return RollupService(harvest=HarvestRepository(db))


def rollup_service(db: Session = Depends(get_db)) -> RollupService:
    return make_rollup_service(db)
