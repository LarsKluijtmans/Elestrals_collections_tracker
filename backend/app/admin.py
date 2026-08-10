"""The shared M2M admin client.

`AdminClient.from_client_credentials(...)` runs the `client_credentials` grant against the
Login API once, then caches and silently refreshes the token. We point it at three services
that all accept the same M2M token:

  * auth_url   -> auth-api (/auth/v1)  — `client.users.get(...)`
  * logs_url   -> logs-api (/logs/v1)  — `client.logs.write([...])`

The client is created lazily and reused for the process. It is never exposed to the browser.
"""
from __future__ import annotations

from functools import lru_cache

from platform_admin import AdminClient

from .config import settings


@lru_cache(maxsize=1)
def get_admin() -> AdminClient:
    if not settings.m2m_client_id or not settings.m2m_client_secret:
        raise RuntimeError(
            "M2M credentials are not set (M2M_CLIENT_ID / M2M_CLIENT_SECRET). "
            "Set them in backend/.env, or disable the features that need them "
            "(ENABLE_ENRICHMENT / ENABLE_PROJECT_LOGGING)."
        )
    return AdminClient.from_client_credentials(
        login_api_url=settings.login_api_url,
        auth_url=settings.auth_api_url,
        logs_url=settings.logs_api_url,           # logs + feature usage
        notifications_url=settings.notifications_api_url,
        storage_url=settings.storage_api_url,
        client_id=settings.m2m_client_id,
        client_secret=settings.m2m_client_secret,
    )
