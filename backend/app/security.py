"""Server-side validation of Login-API access tokens.

This is the resource-server half of the platform: we verify the user's access token
*locally* against the Login API's published JWKS — no call to the auth server on the hot
path. The verification mirrors what the platform's own services do:

  * RS256 only (no algorithm-confusion),
  * pin the issuer (`iss`),
  * do NOT verify `aud` — the platform sets `aud` to the project_id and intentionally
    leaves it unverified by resource servers,
  * require `token_type` in {"access", "m2m"} and a `sub`.

The identity claims we rely on (see login-api `jwt_service.build_user_claims`):
  sub          -> end-user UUID (for an M2M token this is the client_id instead)
  projectId    -> project UUID   (camelCase!)
  companyId    -> company UUID   (camelCase!)
  email / preferred_username / scope / token_type
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from .config import settings

_bearer = HTTPBearer(auto_error=True)


@dataclass
class Principal:
    """The validated caller, distilled from the token claims."""

    sub: str
    project_id: str | None
    company_id: str | None
    email: str | None
    username: str | None
    scope: str
    token_type: str

    @property
    def is_user(self) -> bool:
        """True for a real end-user token (not an M2M client_credentials token)."""
        return self.token_type == "access"


class _JwksCache:
    """Caches the Login API's JWKS, refreshing on a TTL or on an unknown `kid` (key rotation)."""

    def __init__(self, jwks_url: str, ttl_seconds: int) -> None:
        self._url = jwks_url
        self._ttl = ttl_seconds
        self._keys: dict[str, dict] = {}
        self._fetched_at = 0.0
        self._lock = threading.Lock()

    def _refresh(self) -> None:
        resp = httpx.get(self._url, timeout=5.0)
        resp.raise_for_status()
        keys = resp.json().get("keys", [])
        self._keys = {k["kid"]: k for k in keys if "kid" in k}
        self._fetched_at = time.monotonic()

    def get_key(self, kid: str) -> dict | None:
        with self._lock:
            fresh = (time.monotonic() - self._fetched_at) < self._ttl
            if kid in self._keys and fresh:
                return self._keys[kid]
            # Cache miss or stale window -> refetch once (this also handles key rotation).
            self._refresh()
            return self._keys.get(kid)


_jwks = _JwksCache(
    f"{settings.login_api_url.rstrip('/')}/login/v1/.well-known/jwks.json",
    settings.jwks_cache_seconds,
)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def verify_token(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> Principal:
    """FastAPI dependency: validate the Bearer access token and return the `Principal`."""
    token = creds.credentials
    try:
        kid = jwt.get_unverified_header(token).get("kid")
    except JWTError:
        raise _unauthorized("malformed token")
    if not kid:
        raise _unauthorized("token missing kid")

    key = _jwks.get_key(kid)
    if key is None:
        raise _unauthorized("signing key not found")

    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=settings.token_issuer,
            options={"verify_aud": False},
        )
    except JWTError as exc:
        raise _unauthorized(f"token rejected: {exc}")

    if claims.get("token_type") not in ("access", "m2m"):
        raise _unauthorized("unexpected token_type")
    sub = claims.get("sub")
    if not sub:
        raise _unauthorized("token missing sub")

    return Principal(
        sub=sub,
        project_id=claims.get("projectId"),
        company_id=claims.get("companyId"),
        email=claims.get("email"),
        username=claims.get("preferred_username"),
        scope=claims.get("scope", ""),
        token_type=claims["token_type"],
    )
