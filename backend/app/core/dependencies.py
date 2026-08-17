"""DI wiring. Every controller receives its services from here — new service wires go in
this file, never into module-level singletons inside a controller."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..config import settings
from ..repositories.app_log_repository import AppLogRepository
from ..repositories.card_repository import CardRepository
from ..repositories.catalog_import_repository import CatalogImportRepository
from ..repositories.inventory_repository import InventoryRepository
from ..repositories.price_repository import PriceRepository
from ..repositories.printing_repository import PrintingRepository
from ..repositories.set_completion_repository import SetCompletionRepository
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
from ..services.collection_browse_service import CollectionBrowseService
from ..services.bulk_service import BulkService
from ..services.completion_service import CompletionService
from ..services.coverage_service import CoverageService
from ..services.dashboard_service import DashboardService
from ..services.inventory_service import InventoryService
from ..services.import_runner import ImportRunner
from ..services.deletion_service import DeletionService
from ..services.import_service import ImportService
from ..services.notification_service import NotificationService
from ..services.public_profile_service import PublicProfileService
from ..services.profile_service import ProfileService
from ..services.saved_view_service import SavedViewService
from ..services.sealed_service import SealedService
from ..services.snapshot_service import SnapshotService
from ..services.valuation_service import ValuationService
from ..services.wishlist_service import WishlistService
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


def inventory_repository(db: Session = Depends(get_db)) -> InventoryRepository:
    return InventoryRepository(db)


def set_completion_repository(db: Session = Depends(get_db)) -> SetCompletionRepository:
    return SetCompletionRepository(db)


def completion_service(
    completion: SetCompletionRepository = Depends(set_completion_repository),
    sets: SetRepository = Depends(set_repository),
) -> CompletionService:
    return CompletionService(completion, sets)


def inventory_service(
    items: InventoryRepository = Depends(inventory_repository),
    printings: PrintingRepository = Depends(printing_repository),
    completion: CompletionService = Depends(completion_service),
) -> InventoryService:
    return InventoryService(items, printings, completion)


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


# --- Prices (phase 2, read-only across the service boundary) --------------------------
# Everything here reads `elestrals_harvest.price_daily` and nothing else of the harvester's.
# There is no write path and no grant for one — see `models/price_daily.py` and story 019.

def price_repository(db: Session = Depends(get_db)) -> PriceRepository:
    return PriceRepository(db)


def valuation_service(
    prices: PriceRepository = Depends(price_repository),
) -> ValuationService:
    return ValuationService(prices)


# --- Browse (bolt 006) ---------------------------------------------------------------

def collection_browse_service(
    items: InventoryRepository = Depends(inventory_repository),
    cards: CardRepository = Depends(card_repository),
    sets: SetRepository = Depends(set_repository),
) -> CollectionBrowseService:
    return CollectionBrowseService(items, cards, sets)


def bulk_service(
    items: InventoryRepository = Depends(inventory_repository),
    inventory: InventoryService = Depends(inventory_service),
) -> BulkService:
    return BulkService(items, inventory)


def saved_view_service(db: Session = Depends(get_db)) -> SavedViewService:
    return SavedViewService(db)


def dashboard_service(
    items: InventoryRepository = Depends(inventory_repository),
    completion: CompletionService = Depends(completion_service),
    prices: PriceRepository = Depends(price_repository),
) -> DashboardService:
    return DashboardService(items, completion, prices)


def make_snapshot_service(db: Session) -> SnapshotService:
    """From a bare session, because the nightly job runs outside FastAPI's DI graph.

    Same shape as `make_import_runner`, and for the same reason: the scheduled path and any
    hand-run path must be the same object graph rather than two wirings that drift.
    """
    return SnapshotService(db)


def snapshot_service(db: Session = Depends(get_db)) -> SnapshotService:
    return make_snapshot_service(db)


# --- Sealed and wishlist (bolt 007) ---------------------------------------------------

def sealed_service(db: Session = Depends(get_db)) -> SealedService:
    return SealedService(db)


def wishlist_service(db: Session = Depends(get_db)) -> WishlistService:
    return WishlistService(db)


# --- Import / export (bolt 008) -------------------------------------------------------

def import_service(
    db: Session = Depends(get_db),
    inventory: InventoryService = Depends(inventory_service),
) -> ImportService:
    """The commit writes through `InventoryService`, never the repository — so an imported
    row obeys the same merge-on-duplicate and completion recompute a hand-entered one does.
    Bypassing it would let an import produce a collection state the UI cannot."""
    return ImportService(db, inventory)


# --- Account, notifications, sharing (bolt 009) ---------------------------------------

def notification_service(db: Session = Depends(get_db)) -> NotificationService:
    """No sender wired yet — the default raises on the first drain attempt.

    Deliberate: a service configured without a real sender should fail loudly rather than quietly
    mark everything sent. The outbox rows are still written, which is the half that matters, and
    they will deliver once notification-api is reachable and a sender is passed here.
    """
    return NotificationService(db)


def public_profile_service(db: Session = Depends(get_db)) -> PublicProfileService:
    return PublicProfileService(db)


def deletion_service(db: Session = Depends(get_db)) -> DeletionService:
    return DeletionService(db)
