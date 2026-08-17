"""Account data deletion — story 035.

Our GDPR surface is small on purpose, and that is what makes this a real answer rather than a best
effort. Identity lives in the platform; this app holds a `sub`, some preferences and a collection.
So "remove every row keyed on my subject" is complete, and `TABLES` below is the whole list.

Three decisions worth keeping:

**Re-authentication is required**, and it is checked at the controller with a fresh token rather
than trusted from a session that might be hours old. An irreversible action taken on a laptop
somebody walked away from is the case this exists for.

**Execution is delayed.** A confirmed request runs after a grace period, cancellable until then,
because "I changed my mind" is a thing people say and an irreversible button pressed in anger is a
support ticket nobody can resolve.

**The audit record is not personal data.** It stores a *hash* of the subject, so an operator can
prove a specific request completed without being able to read who it was about — story 035's fifth
criterion, and the only way an audit trail survives an erasure without defeating it.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models.base import utc_naive
from ..models.collection_snapshot import CollectionSnapshot
from ..models.deletion_request import GRACE_DAYS, DeletionAudit, DeletionRequest
from ..models.import_job import ImportJob
from ..models.inventory_item import InventoryItem
from ..models.notification import NotificationOutbox, NotificationPreference
from ..models.saved_view import SavedView
from ..models.sealed_inventory_item import SealedInventoryItem
from ..models.set_completion import SetCompletion
from ..models.user_profile import UserProfile
from ..models.wishlist_item import WishlistItem
from .inventory_service import InventoryError

#: **Every table keyed on `user_sub`.** Adding a user-owned table without adding it here is the
#: way this quietly stops being complete, so the list is here rather than scattered across
#: services — one place to check against a schema diff.
TABLES = (
    InventoryItem,
    SetCompletion,
    CollectionSnapshot,
    SavedView,
    SealedInventoryItem,
    WishlistItem,
    ImportJob,          # cascades to import_rows
    NotificationPreference,
    NotificationOutbox,
    UserProfile,        # last: it is the row everything else hangs off conceptually
)


class NoPendingRequest(InventoryError):
    code = "deletion_request_not_found"
    status = 404


class AlreadyRequested(InventoryError):
    code = "deletion_already_requested"
    status = 409


class NotYetDue(InventoryError):
    code = "deletion_not_due"
    status = 409


@dataclass(frozen=True, slots=True)
class DeletionSummary:
    request_id: str
    inventory_rows: int
    other_rows: int


def subject_hash(user_sub: str) -> str:
    """SHA-256 of the subject. One-way, and the audit's only link to a person.

    Unsalted deliberately: a per-record salt would make the hash unverifiable, and the point is
    that somebody holding a `sub` can *confirm* a deletion happened while somebody holding only the
    audit table learns nothing. That is a different threat model from password storage.
    """
    return hashlib.sha256(user_sub.encode("utf-8")).hexdigest()


class DeletionService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def request(self, user_sub: str, *, now: datetime | None = None) -> DeletionRequest:
        # Naive UTC — `execute_after` is compared in `due()` and `execute()`. See `utc_naive`.
        moment = utc_naive(now)
        if self.pending(user_sub) is not None:
            raise AlreadyRequested("you already have a deletion request pending")

        request = DeletionRequest(
            user_sub=user_sub,
            status="pending",
            execute_after=moment + timedelta(days=GRACE_DAYS),
        )
        self._db.add(request)
        self._db.commit()
        return request

    def pending(self, user_sub: str) -> DeletionRequest | None:
        return self._db.scalar(
            select(DeletionRequest).where(
                DeletionRequest.user_sub == user_sub,
                DeletionRequest.status == "pending",
            )
        )

    def cancel(self, user_sub: str) -> DeletionRequest:
        """Story 035's last criterion. Available until the moment it executes."""
        request = self.pending(user_sub)
        if request is None:
            raise NoPendingRequest("you have no deletion request to cancel")
        request.status = "cancelled"
        self._db.commit()
        return request

    def execute(
        self, user_sub: str, *, now: datetime | None = None, force: bool = False,
    ) -> DeletionSummary:
        """Erase everything keyed on this subject, and record that it happened.

        `force` skips the grace period. It exists for the "delete my data now, I mean it" path a
        support request needs — not for the ordinary button, which waits.
        """
        moment = utc_naive(now)
        request = self.pending(user_sub)
        if request is None:
            raise NoPendingRequest("no pending deletion request")
        if not force and request.execute_after > moment:
            raise NotYetDue(
                f"this request executes after {request.execute_after.date().isoformat()}"
            )

        inventory_rows = 0
        other_rows = 0
        for model in TABLES:
            column = model.user_sub
            result = self._db.execute(delete(model).where(column == user_sub))
            count = result.rowcount or 0
            if model is InventoryItem:
                inventory_rows = count
            else:
                other_rows += count

        request.status = "completed"
        request.completed_at = moment
        self._db.flush()

        # Written in the same transaction as the erasure, so there can be no state where the data
        # is gone and nothing recorded that it went.
        self._db.add(DeletionAudit(
            subject_hash=subject_hash(user_sub),
            request_id=request.id,
            inventory_rows=inventory_rows,
            other_rows=other_rows,
        ))
        self._db.commit()

        # The request row itself carries the subject, so it goes too — after the audit is written,
        # and referenced from the audit by id rather than by anything personal.
        self._db.execute(
            delete(DeletionRequest).where(DeletionRequest.user_sub == user_sub)
        )
        self._db.commit()

        return DeletionSummary(
            request_id=request.id, inventory_rows=inventory_rows, other_rows=other_rows,
        )

    def due(self, *, now: datetime | None = None) -> list[DeletionRequest]:
        """Requests whose grace period has elapsed — what a scheduled job would walk."""
        moment = utc_naive(now)
        return list(self._db.scalars(
            select(DeletionRequest).where(
                DeletionRequest.status == "pending",
                DeletionRequest.execute_after <= moment,
            )
        ))

    def verify(self, user_sub: str) -> DeletionAudit | None:
        """Prove an erasure happened, from the subject, without the audit storing it.

        This is the assurance path: somebody who can present the `sub` gets a yes; somebody
        holding only the audit table learns nothing about whose data it was.
        """
        return self._db.scalar(
            select(DeletionAudit)
            .where(DeletionAudit.subject_hash == subject_hash(user_sub))
            .order_by(DeletionAudit.created_at.desc())
        )
