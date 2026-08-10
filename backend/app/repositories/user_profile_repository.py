"""All database access for `user_profiles`.

Every method takes `user_sub` as its **first positional argument** — not as an optional
filter. An unscoped query should be a signature error at authoring time, not a data leak
discovered later.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.user_profile import UserProfile


class UserProfileRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, user_sub: str) -> UserProfile | None:
        return self._db.get(UserProfile, user_sub)

    def create(self, user_sub: str) -> UserProfile:
        profile = UserProfile(user_sub=user_sub)
        self._db.add(profile)
        self._db.commit()
        return profile

    def update(self, user_sub: str, **fields) -> UserProfile | None:
        profile = self.get(user_sub)
        if profile is None:
            return None
        for key, value in fields.items():
            setattr(profile, key, value)
        self._db.commit()
        return profile

    def handle_taken(self, user_sub: str, handle: str) -> bool:
        """True if another subject already holds this handle."""
        stmt = select(UserProfile).where(
            UserProfile.handle == handle, UserProfile.user_sub != user_sub
        )
        return self._db.scalars(stmt).first() is not None
