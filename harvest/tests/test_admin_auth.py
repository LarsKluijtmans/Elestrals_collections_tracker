"""The admin gate — story 023.

The most valuable test here is `test_every_admin_route_carries_the_gate`. Every other test
protects a route that exists today; that one protects the route somebody adds in six months,
which is the failure this design is actually exposed to.

`elestrals:operator` is asserted to be **insufficient**, deliberately. The two scopes exist so
that the person who can re-import the catalog is not automatically the person who can start a
scraper against a site that has asked us not to.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.dependencies import require_admin
from app.core.security import Principal
from app.main import app as real_app


def principal(scope: str, sub: str = "user-1") -> Principal:
    return Principal(
        sub=sub, project_id="p", company_id="c", email=None, username=None,
        scope=scope, token_type="access",
    )


def all_routes(application: FastAPI) -> list:
    """Every route, flattened.

    `include_router` nests routes inside wrapper objects in this FastAPI version, so a flat scan
    of `app.routes` finds none of them — and a test that silently checks an empty list is worse
    than no test, since it passes forever.
    """
    found: list = []
    stack = list(application.routes)
    while stack:
        route = stack.pop()
        # `include_router` wraps its routes in `_IncludedRouter`, which exposes the real router
        # as `original_router`. `routes` covers the plain-mount case.
        nested = getattr(route, "routes", None) or getattr(
            getattr(route, "original_router", None), "routes", None
        )
        if nested:
            stack.extend(nested)
        if getattr(route, "path", None) and hasattr(route, "dependant"):
            found.append(route)
    return found


def admin_routes(application: FastAPI) -> list:
    return [route for route in all_routes(application) if route.path.startswith("/api/v1/admin")]


def test_every_admin_route_carries_the_gate():
    """Enumerated rather than spot-checked. A per-route check is a check a new route can forget,
    and this is what makes "one dependency, every route" a property rather than a habit."""
    routes = admin_routes(real_app)
    assert len(routes) >= 7, "the admin surface should be discovered, not silently empty"

    for route in routes:
        assert require_admin in _flatten(route.dependant), (
            f"{route.path} does not require the admin scope"
        )


def _flatten(dependant) -> list:
    if dependant is None:
        return []
    found = []
    for dep in dependant.dependencies:
        found.append(dep.call)
        found.extend(_flatten(dep))
    return found


def test_only_the_health_route_is_unauthenticated():
    """The shape of the service, asserted: it exists to run scans and to be looked at by an
    admin. Collectors never talk to it — they read `price_daily` through `elestrals-api`."""
    public = sorted({
        route.path for route in all_routes(real_app)
        if route.path.startswith("/api/v1")
        and not route.path.startswith("/api/v1/admin")
        and not route.path.endswith(("openapi.json", "/docs"))
    })

    assert public == ["/api/v1/health"]


class TestTheGateItself:
    def test_the_admin_scope_passes(self):
        assert require_admin(principal("openid elestrals:admin")) is not None

    def test_no_scope_is_refused(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as caught:
            require_admin(principal("openid profile"))
        assert caught.value.status_code == 403

    def test_the_operator_scope_alone_is_refused(self):
        """Two roles, on purpose. Re-importing the catalog and starting a scraper are different
        acts with different consequences."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as caught:
            require_admin(principal("openid elestrals:operator"))
        assert caught.value.status_code == 403

    def test_the_refusal_carries_no_detail(self):
        """`403` with nothing in it. A success-shaped response with the interesting fields
        removed leaks the shape of what the caller cannot see, and teaches the frontend to render
        an empty state that actually means "forbidden"."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as caught:
            require_admin(principal("openid"))
        assert caught.value.detail["error"]["details"] == {}
        assert "admin" in caught.value.detail["error"]["message"].lower()


class TestTheDevelopmentAllowlist:
    def test_a_listed_subject_is_an_admin_outside_production(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "environment", "local")
        monkeypatch.setattr(settings, "harvest_admin_subs", "dev-sub")

        assert require_admin(principal("openid", sub="dev-sub")) is not None

    def test_it_is_inert_in_production(self, monkeypatch):
        """A subject allowlist is a development convenience, not an authorisation system — so it
        cannot become one by an environment variable being set on the wrong machine."""
        from fastapi import HTTPException

        from app.config import settings

        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "harvest_admin_subs", "dev-sub")

        with pytest.raises(HTTPException) as caught:
            require_admin(principal("openid", sub="dev-sub"))
        assert caught.value.status_code == 403


def test_an_unauthenticated_admin_request_is_rejected():
    """End to end through the real app: no bearer token, no admin data."""
    with TestClient(real_app) as client:
        response = client.get("/api/v1/admin/sources")

    assert response.status_code in (401, 403)
