"""`/api/v1/alerts` — story 034.

Alerts live on **this** service, not the harvester: an alert is a user's row and `harvest-api` holds
no grant on user data. The harvester publishes `price_daily`; this reads it, decides, and delivers
through the phase-1 outbox.

Owner-scoped throughout, **404 rather than 403** for somebody else's alert — the same rule every
user-owned surface in this app follows.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..core.dependencies import alert_service, current_principal
from ..models.price_alert import PriceAlert
from ..schemas import (
    AlertEvaluationResponse, CreateAlertRequest, ErrorResponse, PriceAlertModel,
)
from ..security import Principal
from ..services.alert_service import AlertService
from ..services.inventory_service import InventoryError

router = APIRouter(prefix="/api/v1", tags=["alerts"])


def _as_error(exc: InventoryError) -> HTTPException:
    return HTTPException(
        status_code=exc.status,
        detail={"error": {"code": exc.code, "message": str(exc) or exc.code, "details": {}}},
    )


def _view(alert: PriceAlert) -> PriceAlertModel:
    printing = alert.printing
    card = printing.card if printing else None
    set_row = card.set if card else None
    return PriceAlertModel(
        id=alert.id,
        printing_id=alert.printing_id,
        card_id=card.id if card else "",
        name=card.name if card else "(unknown card)",
        set_code=set_row.code if set_row else "",
        direction=alert.direction,
        threshold_cents=alert.threshold_cents,
        currency=alert.currency,
        is_active=alert.is_active,
        last_fired_at=alert.last_fired_at,
        cooldown_until=alert.cooldown_until,
        created_at=alert.created_at,
    )


@router.get("/alerts", response_model=list[PriceAlertModel])
def list_alerts(
    principal: Principal = Depends(current_principal),
    svc: AlertService = Depends(alert_service),
) -> list[PriceAlertModel]:
    return [_view(a) for a in svc.list_for_user(principal.sub)]


@router.post(
    "/alerts", response_model=PriceAlertModel, status_code=201,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def create_alert(
    body: CreateAlertRequest,
    principal: Principal = Depends(current_principal),
    svc: AlertService = Depends(alert_service),
) -> PriceAlertModel:
    try:
        alert = svc.create(
            principal.sub, printing_id=body.printing_id, direction=body.direction,
            threshold_cents=body.threshold_cents, currency=body.currency,
        )
    except InventoryError as exc:
        raise _as_error(exc) from None
    return _view(alert)


@router.patch(
    "/alerts/{alert_id}", response_model=PriceAlertModel,
    summary="Activate or deactivate — stops firing immediately",
    responses={404: {"model": ErrorResponse}},
)
def set_active(
    alert_id: str,
    active: bool = True,
    principal: Principal = Depends(current_principal),
    svc: AlertService = Depends(alert_service),
) -> PriceAlertModel:
    """Deactivating keeps the threshold somebody chose. Deleting throws it away. They are
    different intentions and both are offered."""
    try:
        return _view(svc.set_active(principal.sub, alert_id, active=active))
    except InventoryError as exc:
        raise _as_error(exc) from None


@router.delete("/alerts/{alert_id}", status_code=204, responses={404: {"model": ErrorResponse}})
def delete_alert(
    alert_id: str,
    principal: Principal = Depends(current_principal),
    svc: AlertService = Depends(alert_service),
) -> None:
    try:
        svc.delete(principal.sub, alert_id)
    except InventoryError as exc:
        raise _as_error(exc) from None


@router.post(
    "/alerts/evaluate", response_model=AlertEvaluationResponse,
    summary="Evaluate every active alert against settled rollups",
)
def evaluate(
    _: Principal = Depends(current_principal),
    svc: AlertService = Depends(alert_service),
) -> AlertEvaluationResponse:
    """Normally driven by the job runner **after the rollup has finished** — an alert evaluated
    against a half-written day fires on a partial median, and an alert is a claim that something
    happened.

    Exposed as an endpoint so it can be run by hand while checking a threshold, in the same spirit
    as the harvester's manual rollup: the scheduled path and the hand-run path are the same code.
    """
    result = svc.evaluate()
    return AlertEvaluationResponse(
        considered=result.considered, fired=result.fired,
        skipped_low_confidence=result.skipped_low_confidence,
        in_cooldown=result.in_cooldown,
    )
