"""`user_profiles` — app-owned preferences, keyed on the JWT subject.

Holds **only** what the platform has no opinion on. Email, display name and avatar are
deliberately absent: they belong to the platform and are enriched from auth-api on read, so
there is one less place for personal data to go stale or leak.
"""
from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from .base import TimestampMixin

VISIBILITIES = ("private", "link", "public")
CONDITION_SCALES = ("tcg", "cardmarket")


class UserProfile(Base, TimestampMixin):
    __tablename__ = "user_profiles"

    # The JWT `sub`. Never client-supplied — it is the primary key precisely so that a
    # row cannot exist for a subject we did not validate.
    user_sub: Mapped[str] = mapped_column(String(36), primary_key=True)

    handle: Mapped[str | None] = mapped_column(String(32), unique=True)
    collection_visibility: Mapped[str] = mapped_column(String(16), default="private", nullable=False)
    default_currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    condition_scale: Mapped[str] = mapped_column(String(16), default="tcg", nullable=False)

    # Unguessable token for `link` visibility. Null until link sharing is enabled.
    share_token: Mapped[str | None] = mapped_column(String(43), unique=True)
