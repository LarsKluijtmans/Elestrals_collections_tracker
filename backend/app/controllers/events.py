"""Relay a browser event into logging, stamped with the validated caller.

The browser has no `logs:write` scope and must never talk to logs-api directly. Routing
client events through an authenticated endpoint is what makes the attributed identity
trustworthy — the caller cannot claim to be someone else, and cannot choose its own severity
beyond the narrow set the schema allows.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from ..core.dependencies import current_principal
from ..schemas import ClientEvent
from ..security import Principal
from ..services.logging_service import log_event

router = APIRouter(prefix="/api/v1", tags=["events"])


@router.post("/events", status_code=status.HTTP_204_NO_CONTENT, summary="Relay a client event")
def post_event(
    event: ClientEvent,
    request: Request,
    principal: Principal = Depends(current_principal),
) -> None:
    log_event(
        event.level,
        event.message,
        category="client",
        component=event.component or "browser",
        operation="client-event",
        user_sub=principal.sub,
        request_id=getattr(request.state, "request_id", None),
        context=event.context,
    )
