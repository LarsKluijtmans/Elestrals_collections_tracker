"""Feature-usage metering into the platform's flexible usage stream (logs-api).

The platform already has a metering surface and a console view for it, so building our own
analytics would duplicate it for no gain. `feature` is any string key — no schema change is
needed to add one, which is exactly why the vocabulary is declared here in one place rather
than spelled inline at call sites, where it would sprawl and drift.

Never raises: a metering failure must not fail the request that earned the event.
"""
from __future__ import annotations

import threading

from ..admin import get_admin
from ..config import settings

# The whole vocabulary. Adding a feature means adding a constant here.
INVENTORY_ITEM_ADDED = "inventory.item_added"
INVENTORY_BULK_IMPORTED = "inventory.bulk_imported"
COLLECTION_VALUED = "collection.valued"
CATALOG_SEARCHED = "catalog.searched"
PRICE_ALERT_FIRED = "price.alert_fired"
LISTING_CREATED = "listing.created"

FEATURES = frozenset({
    INVENTORY_ITEM_ADDED, INVENTORY_BULK_IMPORTED, COLLECTION_VALUED,
    CATALOG_SEARCHED, PRICE_ALERT_FIRED, LISTING_CREATED,
})


def usage_track(
    feature: str,
    *,
    project_id: str,
    subject: str,
    quantity: int = 1,
    reference_1: str | None = None,
    reference_2: str | None = None,
    reference_3: str | None = None,
) -> None:
    """Record one feature use. Fire-and-forget; never raises."""
    if not settings.enable_usage_metering:
        return
    if feature not in FEATURES:
        # Unknown key: refuse rather than silently polluting the stream with a typo.
        from .logging_service import log_event
        log_event("warning", f"unknown usage feature key: {feature}",
                  component="usage", operation="track")
        return
    if quantity <= 0:
        return  # a zero-quantity event is noise

    def _send() -> None:
        try:
            get_admin().usage.track(
                project_id, feature, subject=subject, quantity=quantity,
                reference_1=reference_1, reference_2=reference_2, reference_3=reference_3,
            )
        except Exception:
            pass

    threading.Thread(target=_send, name="usage-track", daemon=True).start()
