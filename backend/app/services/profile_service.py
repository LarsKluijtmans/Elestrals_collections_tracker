"""Profile: app-owned preferences merged with platform-owned identity.

We never persist email, display name or avatar — they are read from auth-api on demand and
cached in memory only. One less place for personal data to go stale or leak.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from ..config import settings
from ..models.user_profile import CONDITION_SCALES, VISIBILITIES, UserProfile
from ..repositories.user_profile_repository import UserProfileRepository
from ..security import Principal
from .logging_service import log_event

_ENRICH_TTL = 60.0
_enrich_cache: dict[str, tuple[float, dict]] = {}


class HandleTaken(Exception):
    pass


class InvalidPreference(Exception):
    def __init__(self, field: str, allowed: tuple[str, ...]) -> None:
        self.field, self.allowed = field, allowed
        super().__init__(f"{field} must be one of {', '.join(allowed)}")


@dataclass
class ProfileView:
    user_sub: str
    handle: str | None
    collection_visibility: str
    default_currency: str
    condition_scale: str
    # Platform-owned, read-only here. None when enrichment is off or unavailable.
    email: str | None
    username: str | None
    enriched: bool


class ProfileService:
    def __init__(self, repo: UserProfileRepository) -> None:
        self._repo = repo

    def ensure(self, user_sub: str) -> UserProfile:
        """Lazily create the profile row on first authenticated request."""
        return self._repo.get(user_sub) or self._repo.create(user_sub)

    def _enrich(self, principal: Principal) -> tuple[str | None, str | None, bool]:
        """Fetch identity from auth-api. Degrades to token claims — never fails the request."""
        if not settings.enable_enrichment:
            return principal.email, principal.username, False
        cached = _enrich_cache.get(principal.sub)
        if cached and (time.monotonic() - cached[0]) < _ENRICH_TTL:
            d = cached[1]
            return d.get("email"), d.get("username"), True
        try:
            from ..admin import get_admin
            user = get_admin().users.get(principal.project_id, principal.sub)
            data = {
                "email": getattr(user, "email", None),
                "username": getattr(user, "username", None) or getattr(user, "name", None),
            }
            _enrich_cache[principal.sub] = (time.monotonic(), data)
            return data["email"], data["username"], True
        except Exception as exc:
            log_event("warning", "profile enrichment unavailable; using token claims",
                      component="profile", operation="enrich", user_sub=principal.sub, exc=exc)
            return principal.email, principal.username, False

    def view(self, principal: Principal) -> ProfileView:
        profile = self.ensure(principal.sub)
        email, username, enriched = self._enrich(principal)
        return ProfileView(
            user_sub=profile.user_sub,
            handle=profile.handle,
            collection_visibility=profile.collection_visibility,
            default_currency=profile.default_currency,
            condition_scale=profile.condition_scale,
            email=email, username=username, enriched=enriched,
        )

    def update(self, principal: Principal, patch: dict) -> ProfileView:
        self.ensure(principal.sub)
        fields = {}

        if "handle" in patch and patch["handle"] is not None:
            handle = patch["handle"].strip().lower()
            if self._repo.handle_taken(principal.sub, handle):
                raise HandleTaken(handle)
            fields["handle"] = handle

        for key, allowed in (
            ("collection_visibility", VISIBILITIES),
            ("condition_scale", CONDITION_SCALES),
        ):
            if key in patch and patch[key] is not None:
                if patch[key] not in allowed:
                    raise InvalidPreference(key, allowed)
                fields[key] = patch[key]

        if patch.get("default_currency"):
            cur = patch["default_currency"].upper()
            if len(cur) != 3 or not cur.isalpha():
                raise InvalidPreference("default_currency", ("ISO-4217 code",))
            fields["default_currency"] = cur

        if fields:
            self._repo.update(principal.sub, **fields)
            log_event("info", "profile updated", component="profile", operation="update",
                      user_sub=principal.sub, context={"fields": sorted(fields)})
        return self.view(principal)
