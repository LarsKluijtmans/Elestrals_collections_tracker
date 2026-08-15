"""Assert the M2M service account actually holds every scope this app needs.

Why this exists: platform module calls are best-effort by design — logging, forwarding and
metering all swallow their exceptions so they can never fail a user request. That is correct,
and it also means a **missing RBAC scope is invisible**: the call 403s, the exception is
swallowed, and the feature is silently dead. Nothing surfaces until someone notices a console
view is empty weeks later.

So we check once, at startup, and shout.
"""
from __future__ import annotations

import httpx
from jose import jwt

from ..config import settings

REQUIRED_SCOPES = (
    "users:read",              # profile enrichment (auth-api)
    "logs:write",              # error/security forwarding (logs-api)
    "usage:write",             # feature metering (logs-api)
    "notifications:send",      # phase 1 unit 007
    "notifications:configure",
    "storage:read",            # avatars
    "storage:write",
)


class MissingScopes(RuntimeError):
    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(
            "M2M service account is missing required scope(s): " + ", ".join(missing) +
            ".\nGrant them on the service account's RBAC role, or disable the dependent "
            "features (ENABLE_ENRICHMENT / ENABLE_PROJECT_LOGGING / ENABLE_USAGE_METERING)."
        )


def fetch_granted_scopes(timeout: float = 5.0) -> set[str]:
    """Run client_credentials and read the `scope` claim off the token we get back."""
    resp = httpx.post(
        f"{settings.login_api_url.rstrip('/')}/login/v1/token",
        data={
            "grant_type": "client_credentials",
            "client_id": settings.m2m_client_id,
            "client_secret": settings.m2m_client_secret,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]
    # We just received this over TLS from the issuer; we are reading our own grant, not
    # authenticating a caller, so an unverified decode is appropriate here.
    claims = jwt.get_unverified_claims(token)
    raw = claims.get("scope") or ""
    return set(raw.split()) if isinstance(raw, str) else set(raw)


def assert_m2m_scopes(*, fail_fast: bool) -> None:
    from ..services.logging_service import log_event

    if not settings.m2m_client_id or not settings.m2m_client_secret:
        msg = "M2M credentials not configured; platform-backed features are disabled"
        log_event("warning", msg, component="startup", operation="scope-check")
        if fail_fast and (settings.enable_enrichment or settings.enable_project_logging):
            raise RuntimeError(
                msg + ". Set M2M_CLIENT_ID / M2M_CLIENT_SECRET in backend/.env, or turn the "
                "dependent features off explicitly."
            )
        return

    try:
        granted = fetch_granted_scopes()
    except Exception as exc:
        # The platform being down at startup is not a reason to refuse to boot — sign-in
        # will fail loudly on its own, and every other feature degrades by design.
        log_event("warning", "could not verify M2M scopes (platform unreachable?)",
                  component="startup", operation="scope-check", exc=exc)
        return

    missing = [s for s in REQUIRED_SCOPES if s not in granted]
    if not missing:
        log_event("info", "M2M scope check passed",
                  component="startup", operation="scope-check",
                  context={"scopes": len(REQUIRED_SCOPES)})
        return

    err = MissingScopes(missing)
    log_event("error", str(err), component="startup", operation="scope-check",
              context={"missing": missing})
    if fail_fast:
        raise err
