"""`deletion_requests` and `deletion_audits` — story 035.

Our GDPR surface is small on purpose, and that is what makes this tractable. Identity lives in the
platform; this app holds a `sub`, some preferences, and a collection. So "delete everything keyed on
my subject" is a real, complete answer here rather than a best effort.

**Two tables, and the split is the point.** The request is personal data and goes when the deletion
runs. The audit is not: it records that *a* deletion happened, when, and how many rows — with the
subject hashed rather than stored. An operator can prove the erasure occurred without being able to
read who it was about, which is exactly what story 035's fifth criterion asks for.

The delay is deliberate too. A confirmed request executes after a grace period rather than
immediately, because "I changed my mind" is a thing people say and an irreversible button pressed in
anger is a support ticket nobody can resolve.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from .base import TimestampMixin, UuidPrimaryKeyMixin

STATUSES = ("pending", "cancelled", "completed")

#: Story 035 says "within 30 days". This is the *grace* period before execution, not the deadline —
#: it leaves plenty of room and gives somebody a week to change their mind.
GRACE_DAYS = 7


class DeletionRequest(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "deletion_requests"

    user_sub: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")

    #: When the request becomes executable. Cancellable until then.
    execute_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_deletion_requests_user", "user_sub", "status"),
        Index("ix_deletion_requests_due", "status", "execute_after"),
    )


class DeletionAudit(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "deletion_audits"

    #: **A hash, never the subject.** This row outlives the deletion, so storing the `sub` would
    #: mean the erasure did not erase. The hash is enough to prove a specific request completed
    #: when somebody presents the id; it is not enough to work out who from.
    subject_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)

    #: Counts only. Useful for assurance, personal about nobody.
    inventory_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    other_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (Index("ix_deletion_audits_request", "request_id"),)
