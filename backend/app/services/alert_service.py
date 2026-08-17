"""Price alerts — story 034, and the first thing to ride bolt 009's outbox.

Four rules, and three of them are refusals.

**Nothing fires on `low` confidence.** Under ADR-004 more of the data is thin, single-source or
derived from asking prices, and firing on that would train users to ignore alerts — at which point
the feature is worse than absent, because the ones that matter get ignored too.

**Nothing fires twice inside the cooldown.** A price oscillating around a threshold would otherwise
produce a notification every evaluation. One is information; six is a reason to mute the channel.

**Evaluation runs after the rollup, never on its own schedule.** An alert evaluated against a
half-written day fires on a partial median, and an alert is a *claim that something happened*.

And the one thing it does rather than refuses: **the message states the price, the window and the
confidence.** "Vipyro crossed €20" cannot be acted on. "Vipyro's median crossed €20, from 6 sales
across 2 sources" can — a collector can go and look.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.base import utc_naive
from ..models.price_alert import COOLDOWN_DAYS, DIRECTIONS, PriceAlert
from ..repositories.price_repository import PriceRepository
from .inventory_service import InventoryError
from .notification_service import NotificationService

#: Story 034: nothing fires on data this thin. `low` covers anything derived from asking prices
#: however much of it there is, which is exactly the material ADR-004 made more common.
MIN_CONFIDENCE = ("medium", "high")


class AlertNotFound(InventoryError):
    code = "price_alert_not_found"
    status = 404


class InvalidAlert(InventoryError):
    code = "bad_request"
    status = 400


class DuplicateAlert(InventoryError):
    code = "price_alert_exists"
    status = 409


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    considered: int
    fired: int
    #: Skipped because the data was too thin to make a claim on. Reported rather than swallowed —
    #: an alert that never fires because its card is never confidently priced is worth knowing
    #: about, and this is the number that would show it.
    skipped_low_confidence: int
    in_cooldown: int


class AlertService:
    def __init__(
        self, db: Session, prices: PriceRepository, notifications: NotificationService,
    ) -> None:
        self._db = db
        self._prices = prices
        self._notifications = notifications

    # --- managing alerts --------------------------------------------------------------

    def list_for_user(self, user_sub: str) -> list[PriceAlert]:
        return list(self._db.scalars(
            select(PriceAlert)
            .where(PriceAlert.user_sub == user_sub)
            .order_by(PriceAlert.created_at.desc())
        ))

    def create(
        self, user_sub: str, *, printing_id: str, direction: str,
        threshold_cents: int, currency: str = "EUR",
    ) -> PriceAlert:
        if direction not in DIRECTIONS:
            raise InvalidAlert(f"direction must be one of {DIRECTIONS}")
        if threshold_cents <= 0:
            raise InvalidAlert("a threshold must be more than nothing")

        existing = self._db.scalar(
            select(PriceAlert).where(
                PriceAlert.user_sub == user_sub,
                PriceAlert.printing_id == printing_id,
                PriceAlert.direction == direction,
            )
        )
        if existing is not None:
            raise DuplicateAlert(
                f"you already have an alert for when this goes {direction} a price"
            )

        alert = PriceAlert(
            user_sub=user_sub, printing_id=printing_id, direction=direction,
            threshold_cents=threshold_cents, currency=currency.upper(),
        )
        self._db.add(alert)
        self._db.commit()

        # **Setting an alert is the opt-in.** Story 032's defaults leave `price_alert` on `none`
        # until asked, and creating an alert *is* asking — without this, somebody sets a threshold,
        # the alert fires, `enqueue` drops it as muted, and nothing arrives. A silent feature is
        # worse than an absent one.
        #
        # `inapp` rather than `email`: the least intrusive channel that still works, and the
        # settings page is one click away for anybody who wants mail instead.
        if self._notifications.preferences(user_sub)["price_alert"] == "none":
            self._notifications.set_preference(
                user_sub, event_type="price_alert", channel="inapp",
            )

        return alert

    def get(self, user_sub: str, alert_id: str) -> PriceAlert:
        alert = self._db.scalar(
            select(PriceAlert).where(
                PriceAlert.user_sub == user_sub, PriceAlert.id == alert_id
            )
        )
        if alert is None:
            raise AlertNotFound(alert_id)
        return alert

    def set_active(self, user_sub: str, alert_id: str, *, active: bool) -> PriceAlert:
        """Deactivating stops it firing **immediately** — the evaluation only looks at active
        rows, so there is no window in which a switched-off alert can still go off."""
        alert = self.get(user_sub, alert_id)
        alert.is_active = active
        self._db.commit()
        return alert

    def delete(self, user_sub: str, alert_id: str) -> None:
        alert = self.get(user_sub, alert_id)
        self._db.delete(alert)
        self._db.commit()

    # --- evaluation -------------------------------------------------------------------

    def evaluate(self, *, now=None, currency: str = "EUR") -> EvaluationResult:
        """Fire every active alert whose threshold has been crossed on settled data.

        Called as the **final step of the rollup**, not on a schedule of its own. Anything else
        risks evaluating a half-written day, and firing on a partial median is making a claim that
        something happened when it may not have.
        """
        moment = utc_naive(now)
        active = list(self._db.scalars(
            select(PriceAlert).where(PriceAlert.is_active.is_(True))
        ))
        if not active:
            return EvaluationResult(0, 0, 0, 0)

        rollups = self._prices.latest_for_printings(
            sorted({a.printing_id for a in active}), currency=currency,
        )

        fired = thin = cooling = 0
        for alert in active:
            if alert.cooldown_until is not None and alert.cooldown_until > moment:
                cooling += 1
                continue

            row = rollups.get((alert.printing_id, "")) or next(
                (v for (pid, _), v in rollups.items() if pid == alert.printing_id), None,
            )
            if row is None or row.median_cents is None:
                continue

            if row.confidence not in MIN_CONFIDENCE:
                # Not a failure and not silence: counted, so "my alert never fires" has an
                # answer other than "it is broken".
                thin += 1
                continue

            crossed = (
                row.median_cents <= alert.threshold_cents if alert.direction == "below"
                else row.median_cents >= alert.threshold_cents
            )
            if not crossed:
                continue

            self._notifications.enqueue(
                alert.user_sub,
                event_type="price_alert",
                subject=self._subject(alert, row),
                body=self._body(alert, row),
            )
            alert.last_fired_at = moment
            alert.cooldown_until = moment + timedelta(days=COOLDOWN_DAYS)
            fired += 1

        self._db.commit()
        return EvaluationResult(
            considered=len(active), fired=fired,
            skipped_low_confidence=thin, in_cooldown=cooling,
        )

    # --- the message ------------------------------------------------------------------

    def _subject(self, alert: PriceAlert, row) -> str:
        printing = alert.printing
        card = printing.card if printing else None
        name = card.name if card else "A card you are watching"
        return f"{name} is {alert.direction} {_money(alert.threshold_cents, alert.currency)}"

    def _body(self, alert: PriceAlert, row) -> str:
        """**Price, window and confidence** — story 034's fourth criterion, and what makes an
        alert checkable rather than merely startling.

        "Vipyro crossed €20" cannot be acted on. "Vipyro's median is €18.50, from 6 sales across
        2 sources on 15 August" can: the reader can go and look at the same data.
        """
        printing = alert.printing
        card = printing.card if printing else None
        name = card.name if card else "A card you are watching"
        sources = getattr(row, "source_count", None)

        parts = [
            f"{name} has a median of {_money(int(row.median_cents), row.currency)}",
            f"which is {alert.direction} your {_money(alert.threshold_cents, alert.currency)} "
            f"threshold.",
            f"That figure is from {row.observation_count} "
            f"{'sale' if row.observation_count == 1 else 'sales'}",
        ]
        if sources:
            parts.append(f"across {sources} {'source' if sources == 1 else 'sources'}")
        parts.append(f"on {row.day.isoformat()}, confidence {row.confidence}.")
        return " ".join(parts)


def _money(cents: int, currency: str) -> str:
    return f"{currency} {cents / 100:,.2f}"
