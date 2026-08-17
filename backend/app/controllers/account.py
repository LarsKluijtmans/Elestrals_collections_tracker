"""`/api/v1/notifications`, `/api/v1/account/*` and the public `/api/v1/u/{handle}` — bolt 009.

Three surfaces, three rules worth reading before changing anything here.

**The public collection is built from a whitelist model.** `PublicHolding` never had cost basis,
acquisition price, storage location or notes, so a future column on `inventory_items` cannot leak
through this route. Filtering would have been a rule someone forgets; a separate model is a rule
that enforces itself.

**A private collection is 404, not 403.** A 403 confirms the handle exists, which is an enumeration
oracle over who has an account here.

**Deletion needs a fresh token.** `X-Reauth-Token` is checked against the same JWKS as the bearer
and must be newer than the configured window — an irreversible action taken on a laptop somebody
walked away from is the case that exists for.
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from ..core.dependencies import (
    current_principal,
    deletion_service,
    notification_service,
    profile_service,
    public_profile_service,
)
from ..schemas import (
    DeletionRequestResponse,
    DeletionSummaryResponse,
    ErrorResponse,
    NotificationInboxResponse,
    NotificationPreferencesResponse,
    OutboxEntryModel,
    PublicCollectionResponse,
    PublicHoldingModel,
    SetPreferenceRequest,
    ShareTokenResponse,
    TestNotificationRequest,
)
from ..security import Principal
from ..services.deletion_service import DeletionService
from ..services.inventory_service import InventoryError
from ..services.notification_service import NotificationService
from ..services.profile_service import ProfileService
from ..services.public_profile_service import PublicProfileService

router = APIRouter(prefix="/api/v1", tags=["account"])


def _err(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status,
                         detail={"error": {"code": code, "message": message, "details": {}}})


def _as_error(exc: InventoryError) -> HTTPException:
    return _err(exc.status, exc.code, str(exc) or exc.code)


# --- notifications -------------------------------------------------------------------


@router.get("/notifications/preferences", response_model=NotificationPreferencesResponse)
def get_preferences(
    principal: Principal = Depends(current_principal),
    svc: NotificationService = Depends(notification_service),
) -> NotificationPreferencesResponse:
    """Every event type with its channel, defaults included.

    The full set rather than only what is stored, so a client never has to know the defaults — and
    so adding an event type does not need a migration to backfill rows nobody has an opinion about.
    """
    return NotificationPreferencesResponse(preferences=svc.preferences(principal.sub))


@router.put(
    "/notifications/preferences", response_model=NotificationPreferencesResponse,
    responses={400: {"model": ErrorResponse}},
)
def set_preference(
    body: SetPreferenceRequest,
    principal: Principal = Depends(current_principal),
    svc: NotificationService = Depends(notification_service),
) -> NotificationPreferencesResponse:
    try:
        return NotificationPreferencesResponse(
            preferences=svc.set_preference(
                principal.sub, event_type=body.event_type, channel=body.channel,
            )
        )
    except InventoryError as exc:
        raise _as_error(exc) from None


@router.post(
    "/notifications/test", response_model=OutboxEntryModel | None,
    summary="Queue a test notification on the chosen channel",
    responses={400: {"model": ErrorResponse}},
)
def send_test(
    body: TestNotificationRequest,
    principal: Principal = Depends(current_principal),
    svc: NotificationService = Depends(notification_service),
) -> OutboxEntryModel | None:
    """Queues rather than sends. That is not a shortcut — it is the same path a real notification
    takes, so a test that arrives proves the whole chain including the outbox, and a test that
    does not arrive leaves a row an operator can look at."""
    try:
        entry = svc.enqueue(
            principal.sub, event_type="account",
            subject="Test notification",
            body="If you are reading this, notifications are working.",
            channel=body.channel,
        )
    except InventoryError as exc:
        raise _as_error(exc) from None
    return _outbox_view(entry) if entry else None


@router.get("/notifications/inbox", response_model=NotificationInboxResponse)
def inbox(
    principal: Principal = Depends(current_principal),
    svc: NotificationService = Depends(notification_service),
) -> NotificationInboxResponse:
    entries = svc.for_user(principal.sub)
    return NotificationInboxResponse(
        items=[_outbox_view(e) for e in entries],
        pending=sum(1 for e in entries if e.status == "pending"),
    )


def _outbox_view(entry) -> OutboxEntryModel:
    return OutboxEntryModel(
        id=entry.id, event_type=entry.event_type, channel=entry.channel,
        subject=entry.subject, body=entry.body, status=entry.status,
        attempts=entry.attempts, last_error=entry.last_error,
        sent_at=entry.sent_at, created_at=entry.created_at,
    )


# --- sharing -------------------------------------------------------------------------


@router.post("/account/share-token", response_model=ShareTokenResponse)
def rotate_share_token(
    principal: Principal = Depends(current_principal),
    profiles: ProfileService = Depends(profile_service),
    public: PublicProfileService = Depends(public_profile_service),
) -> ShareTokenResponse:
    """Mint a new share token, invalidating the old one.

    Rotation is the only revocation a shared link has — there is no way to un-send a URL — so this
    is deliberately a single obvious action rather than buried in settings.
    """
    profile = profiles.ensure(principal.sub)
    token = public.rotate_share_token(profile)
    return ShareTokenResponse(share_token=token)


@router.get(
    "/u/{handle}", response_model=PublicCollectionResponse,
    summary="A public collection — whitelist projection, no session required",
    responses={404: {"model": ErrorResponse}},
)
def public_collection(
    handle: str,
    public: PublicProfileService = Depends(public_profile_service),
) -> PublicCollectionResponse:
    """**404 for anything not public**, including a `link`-shared collection reached by handle —
    otherwise the token would be pointless. A 403 would confirm the handle exists."""
    collection = public.by_handle(handle)
    if collection is None:
        raise _err(404, "not_found", "No such collection")
    return _public_view(collection)


@router.get(
    "/shared", response_model=PublicCollectionResponse,
    summary="A link-shared collection, by token",
    responses={404: {"model": ErrorResponse}},
)
def shared_collection(
    token: str = Query(min_length=8, max_length=64),
    public: PublicProfileService = Depends(public_profile_service),
) -> PublicCollectionResponse:
    collection = public.by_share_token(token)
    if collection is None:
        raise _err(404, "not_found", "No such collection")
    return _public_view(collection)


def _public_view(collection) -> PublicCollectionResponse:
    return PublicCollectionResponse(
        handle=collection.handle,
        total_items=collection.total_items,
        distinct_printings=collection.distinct_printings,
        # `asdict` over the whitelist dataclass. There is no inventory row in scope here to
        # accidentally spread, which is the point of building through `PublicHolding` at all.
        holdings=[PublicHoldingModel(**asdict(h)) for h in collection.holdings],
        unlisted=collection.unlisted,
    )


# --- deletion ------------------------------------------------------------------------


def _require_reauth(
    principal: Principal,
    reauth_token: str | None,
) -> None:
    """Deletion needs a *fresh* proof of identity, not a session from this morning.

    The token is verified against the same JWKS as the bearer and must belong to the same subject.
    Freshness is what matters: an irreversible action taken on an unattended laptop is exactly the
    case this exists for, and a long-lived session cannot distinguish it.
    """
    from ..security import verify_raw_token

    if not reauth_token:
        raise _err(401, "reauth_required", "Confirm your identity to continue")
    try:
        fresh = verify_raw_token(reauth_token)
    except Exception:  # noqa: BLE001 — any verification failure is the same answer
        raise _err(401, "reauth_required", "That confirmation could not be verified") from None
    if fresh.sub != principal.sub:
        raise _err(401, "reauth_required", "That confirmation is for a different account")


@router.get("/account/deletion", response_model=DeletionRequestResponse | None)
def get_deletion(
    principal: Principal = Depends(current_principal),
    svc: DeletionService = Depends(deletion_service),
) -> DeletionRequestResponse | None:
    request = svc.pending(principal.sub)
    if request is None:
        return None
    return DeletionRequestResponse(
        id=request.id, status=request.status, execute_after=request.execute_after,
        created_at=request.created_at,
    )


@router.post(
    "/account/deletion", response_model=DeletionRequestResponse, status_code=201,
    summary="Request deletion — requires re-authentication",
    responses={401: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def request_deletion(
    principal: Principal = Depends(current_principal),
    reauth_token: str | None = Header(default=None, alias="X-Reauth-Token"),
    svc: DeletionService = Depends(deletion_service),
    notifications: NotificationService = Depends(notification_service),
) -> DeletionRequestResponse:
    _require_reauth(principal, reauth_token)
    try:
        request = svc.request(principal.sub)
    except InventoryError as exc:
        raise _as_error(exc) from None

    # Account-critical, so it goes out whatever the user's preferences say — and through the
    # outbox like everything else, so an API outage delays the confirmation rather than losing it.
    notifications.enqueue(
        principal.sub, event_type="account",
        subject="Your deletion request",
        body=(
            f"Everything in your Elestral Vault collection will be removed after "
            f"{request.execute_after.date().isoformat()}. You can cancel until then."
        ),
    )
    return DeletionRequestResponse(
        id=request.id, status=request.status, execute_after=request.execute_after,
        created_at=request.created_at,
    )


@router.delete(
    "/account/deletion", response_model=DeletionRequestResponse,
    summary="Cancel a pending deletion request",
    responses={404: {"model": ErrorResponse}},
)
def cancel_deletion(
    principal: Principal = Depends(current_principal),
    svc: DeletionService = Depends(deletion_service),
) -> DeletionRequestResponse:
    """No re-authentication here, deliberately. Cancelling is the *safe* direction, and putting a
    hurdle in front of stopping an irreversible action gets the hurdle wrong."""
    try:
        request = svc.cancel(principal.sub)
    except InventoryError as exc:
        raise _as_error(exc) from None
    return DeletionRequestResponse(
        id=request.id, status=request.status, execute_after=request.execute_after,
        created_at=request.created_at,
    )


@router.post(
    "/account/deletion/execute", response_model=DeletionSummaryResponse,
    summary="Run a due deletion now",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse},
               409: {"model": ErrorResponse}},
)
def execute_deletion(
    principal: Principal = Depends(current_principal),
    reauth_token: str | None = Header(default=None, alias="X-Reauth-Token"),
    svc: DeletionService = Depends(deletion_service),
) -> DeletionSummaryResponse:
    """Skips the remaining grace period on the user's own say-so, with a fresh token.

    "Delete my data now, I mean it" is a real request, and making somebody wait a week after they
    have re-authenticated to say so twice is ceremony rather than safety.
    """
    _require_reauth(principal, reauth_token)
    try:
        summary = svc.execute(principal.sub, force=True)
    except InventoryError as exc:
        raise _as_error(exc) from None
    return DeletionSummaryResponse(
        request_id=summary.request_id,
        inventory_rows=summary.inventory_rows,
        other_rows=summary.other_rows,
    )
