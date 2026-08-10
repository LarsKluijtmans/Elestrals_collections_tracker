"""DI wiring. Every controller receives its services from here — new service wires go in
this file, never into module-level singletons inside a controller."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..config import settings
from ..repositories.app_log_repository import AppLogRepository
from ..repositories.card_repository import CardRepository
from ..repositories.catalog_import_repository import CatalogImportRepository
from ..repositories.printing_repository import PrintingRepository
from ..repositories.set_repository import SetRepository
from ..repositories.user_profile_repository import UserProfileRepository
from ..security import Principal, verify_token
from ..services.catalog_health_service import CatalogHealthService
from ..services.catalog_read_service import (
    CardDetailService,
    CardSearchService,
    SetBrowseService,
)
from ..services.catalog_upsert import CatalogUpsert
from ..services.coverage_service import CoverageService
from ..services.import_runner import ImportRunner
from ..services.profile_service import ProfileService
from .db import get_db


def current_principal(request: Request, principal: Principal = Depends(verify_token)) -> Principal:
    """Validate the bearer token and stash the caller so the logging middleware can
    attribute the request without re-parsing it."""
    request.state.principal = principal
    return principal


def user_profile_repository(db: Session = Depends(get_db)) -> UserProfileRepository:
    return UserProfileRepository(db)


def app_log_repository(db: Session = Depends(get_db)) -> AppLogRepository:
    return AppLogRepository(db)


def profile_service(
    repo: UserProfileRepository = Depends(user_profile_repository),
) -> ProfileService:
    return ProfileService(repo)


# --- Operator access ---------------------------------------------------------------

def require_operator(principal: Principal = Depends(current_principal)) -> Principal:
    """Guard for `/api/v1/admin/*`.

    A non-operator gets 403 with no body detail — never a 200 with the interesting fields
    filtered out, which leaks the shape of what they cannot see.
    """
    scopes = principal.scope.split()
    if settings.operator_scope in scopes or principal.sub in settings.operator_subs_list:
        return principal
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"error": {"code": "forbidden", "message": "Operator access required",
                          "details": {}}},
    )


# --- Catalog ------------------------------------------------------------------------

def set_repository(db: Session = Depends(get_db)) -> SetRepository:
    return SetRepository(db)


def card_repository(db: Session = Depends(get_db)) -> CardRepository:
    return CardRepository(db)


def printing_repository(db: Session = Depends(get_db)) -> PrintingRepository:
    return PrintingRepository(db)


def catalog_import_repository(db: Session = Depends(get_db)) -> CatalogImportRepository:
    return CatalogImportRepository(db)


def coverage_service(
    sets: SetRepository = Depends(set_repository),
    cards: CardRepository = Depends(card_repository),
) -> CoverageService:
    return CoverageService(sets, cards)


def card_search_service(
    cards: CardRepository = Depends(card_repository),
    printings: PrintingRepository = Depends(printing_repository),
) -> CardSearchService:
    return CardSearchService(cards, printings)


def card_detail_service(
    cards: CardRepository = Depends(card_repository),
    sets: SetRepository = Depends(set_repository),
) -> CardDetailService:
    return CardDetailService(cards, sets)


def set_browse_service(
    sets: SetRepository = Depends(set_repository),
    cards: CardRepository = Depends(card_repository),
    printings: PrintingRepository = Depends(printing_repository),
) -> SetBrowseService:
    return SetBrowseService(sets, cards, printings)


def catalog_health_service(
    imports: CatalogImportRepository = Depends(catalog_import_repository),
    sets: SetRepository = Depends(set_repository),
    cards: CardRepository = Depends(card_repository),
) -> CatalogHealthService:
    return CatalogHealthService(imports, sets, cards)


def make_import_runner(db: Session) -> ImportRunner:
    """Compose a runner from a bare session.

    Used by the CLI, which lives outside FastAPI's DI graph, and by `import_runner` below —
    so the scheduled path and the operator-triggered path are the same object graph rather
    than two wirings that drift.
    """
    sets = SetRepository(db)
    cards = CardRepository(db)
    return ImportRunner(
        sets=sets,
        cards=cards,
        imports=CatalogImportRepository(db),
        upsert=CatalogUpsert(cards),
        coverage=CoverageService(sets, cards),
    )


def import_runner(db: Session = Depends(get_db)) -> ImportRunner:
    return make_import_runner(db)
