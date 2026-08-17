"""The account, notification and sharing routes — bolt 009 over HTTP.

The route-level assertions worth having are the ones the service cannot make: that a private
collection answers **404 and not 403**, that deletion refuses without a fresh token, and that the
public JSON carries nothing private even when the underlying row does.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.user_profile import UserProfile
from app.security import Principal, verify_token
from test_inventory import ALICE, BOB, build_service, seed_catalog


def principal(sub: str) -> Principal:
    return Principal(sub=sub, project_id="p", company_id="c", email=None,
                     username=None, scope="", token_type="access")


@pytest.fixture()
def catalog(db):
    return seed_catalog(db, card_count=3)


@pytest.fixture()
def api(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[verify_token] = lambda: principal(ALICE)
    yield TestClient(app)
    app.dependency_overrides.clear()


def as_bob():
    app.dependency_overrides[verify_token] = lambda: principal(BOB)


def profile(db, user_sub=ALICE, **kwargs) -> UserProfile:
    row = UserProfile(user_sub=user_sub, **kwargs)
    db.add(row)
    db.commit()
    return row


# --- notifications -------------------------------------------------------------------

def test_preferences_start_conservative(api):
    prefs = api.get("/api/v1/notifications/preferences").json()["preferences"]
    assert prefs["account"] == "email"
    assert prefs["price_alert"] == "none"


def test_setting_a_preference_over_http(api):
    body = api.put("/api/v1/notifications/preferences", json={
        "event_type": "price_alert", "channel": "email",
    }).json()
    assert body["preferences"]["price_alert"] == "email"


def test_muting_account_notifications_is_400(api):
    response = api.put("/api/v1/notifications/preferences", json={
        "event_type": "account", "channel": "none",
    })
    assert response.status_code == 400


def test_an_unknown_event_type_is_400(api):
    assert api.put("/api/v1/notifications/preferences", json={
        "event_type": "birthday", "channel": "email",
    }).status_code == 400


def test_a_test_notification_lands_in_the_outbox(api):
    """Queued rather than sent, and that is the same path a real notification takes — so a test
    that arrives proves the whole chain, and one that does not leaves a row to look at."""
    entry = api.post("/api/v1/notifications/test", json={"channel": "email"}).json()

    assert entry["status"] == "pending"
    assert api.get("/api/v1/notifications/inbox").json()["pending"] == 1


def test_the_inbox_is_owner_scoped(api):
    api.post("/api/v1/notifications/test", json={"channel": "email"})
    as_bob()
    assert api.get("/api/v1/notifications/inbox").json()["items"] == []


# --- the public collection -----------------------------------------------------------

def test_a_public_collection_is_readable_without_a_session(api, db, catalog):
    profile(db, handle="alice", collection_visibility="public")
    build_service(db).add(ALICE, printing_id=catalog["printings"]["BS1-001:common"], quantity=2)

    # No `verify_token` override needed — the route takes no principal at all.
    body = api.get("/api/v1/u/alice").json()
    assert body["handle"] == "alice"
    assert body["total_items"] == 2


def test_a_private_collection_is_404_not_403(api, db):
    """A 403 would confirm the handle exists, which is an enumeration oracle over who has an
    account here."""
    profile(db, handle="alice", collection_visibility="private")
    response = api.get("/api/v1/u/alice")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_an_unknown_handle_is_the_same_404(api, db):
    """Identical to the private case, deliberately — otherwise the difference between the two
    responses is the oracle."""
    profile(db, handle="alice", collection_visibility="private")
    assert api.get("/api/v1/u/nobody").status_code == 404
    assert api.get("/api/v1/u/alice").status_code == 404


def test_the_public_response_carries_nothing_private(api, db, catalog):
    """Even when the underlying row has all of it. The whitelist model is asserted structurally
    in `test_account.py`; this proves the JSON on the wire."""
    profile(db, handle="alice", collection_visibility="public")
    build_service(db).add(
        ALICE, printing_id=catalog["printings"]["BS1-001:common"],
        acquired_unit_price_cents=99_999, acquired_currency="EUR",
        storage_location="the safe", notes="a secret",
    )

    raw = api.get("/api/v1/u/alice").text
    assert "99999" not in raw
    assert "the safe" not in raw
    assert "a secret" not in raw

    (holding,) = api.get("/api/v1/u/alice").json()["holdings"]
    assert set(holding) == {
        "printing_id", "card_id", "name", "set_code", "collector_number",
        "element", "rarity", "finish", "condition", "quantity",
    }


def test_a_share_token_reaches_a_link_shared_collection(api, db, catalog):
    profile(db, handle="alice", collection_visibility="link")
    build_service(db).add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])

    token = api.post("/api/v1/account/share-token").json()["share_token"]

    body = api.get(f"/api/v1/shared?token={token}").json()
    assert body["unlisted"] is True
    assert body["total_items"] == 1


def test_a_bad_share_token_is_404(api, db):
    profile(db, handle="alice", collection_visibility="link")
    assert api.get("/api/v1/shared?token=" + "x" * 32).status_code == 404


def test_a_link_shared_collection_is_404_by_handle(api, db):
    """Or the token would be pointless."""
    profile(db, handle="alice", collection_visibility="link")
    assert api.get("/api/v1/u/alice").status_code == 404


# --- deletion ------------------------------------------------------------------------

def test_requesting_deletion_without_reauth_is_401(api):
    """An irreversible action taken on an unattended laptop is the case this exists for, and a
    session from this morning cannot distinguish it."""
    response = api.post("/api/v1/account/deletion")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "reauth_required"


def test_an_unverifiable_reauth_token_is_401(api):
    response = api.post("/api/v1/account/deletion",
                        headers={"X-Reauth-Token": "not-a-jwt"})
    assert response.status_code == 401


def test_requesting_deletion_with_a_fresh_token(api, monkeypatch):
    monkeypatch.setattr(
        "app.security.verify_raw_token", lambda token: principal(ALICE),
    )
    response = api.post("/api/v1/account/deletion",
                        headers={"X-Reauth-Token": "fresh"})

    assert response.status_code == 201
    assert response.json()["status"] == "pending"


def test_a_reauth_token_for_another_account_is_401(api, monkeypatch):
    """Presenting somebody else's fresh token must not delete this account."""
    monkeypatch.setattr(
        "app.security.verify_raw_token", lambda token: principal(BOB),
    )
    assert api.post("/api/v1/account/deletion",
                    headers={"X-Reauth-Token": "theirs"}).status_code == 401


def test_a_deletion_request_queues_a_confirmation(api, monkeypatch):
    """Account-critical, so it goes out whatever the preferences say — and through the outbox
    like everything else, so an API outage delays the confirmation rather than losing it."""
    monkeypatch.setattr("app.security.verify_raw_token", lambda token: principal(ALICE))
    api.post("/api/v1/account/deletion", headers={"X-Reauth-Token": "fresh"})

    inbox = api.get("/api/v1/notifications/inbox").json()
    assert any("deletion" in e["subject"].lower() for e in inbox["items"])


def test_cancelling_needs_no_reauth(api, monkeypatch):
    """Cancelling is the *safe* direction. Putting a hurdle in front of stopping an irreversible
    action gets the hurdle exactly backwards."""
    monkeypatch.setattr("app.security.verify_raw_token", lambda token: principal(ALICE))
    api.post("/api/v1/account/deletion", headers={"X-Reauth-Token": "fresh"})

    assert api.delete("/api/v1/account/deletion").json()["status"] == "cancelled"


def test_cancelling_nothing_is_404(api):
    assert api.delete("/api/v1/account/deletion").status_code == 404


def test_the_pending_request_is_readable(api, monkeypatch):
    monkeypatch.setattr("app.security.verify_raw_token", lambda token: principal(ALICE))
    assert api.get("/api/v1/account/deletion").json() is None

    api.post("/api/v1/account/deletion", headers={"X-Reauth-Token": "fresh"})
    assert api.get("/api/v1/account/deletion").json()["status"] == "pending"


def test_executing_erases_and_reports(api, db, catalog, monkeypatch):
    monkeypatch.setattr("app.security.verify_raw_token", lambda token: principal(ALICE))
    build_service(db).add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])
    api.post("/api/v1/account/deletion", headers={"X-Reauth-Token": "fresh"})

    summary = api.post("/api/v1/account/deletion/execute",
                       headers={"X-Reauth-Token": "fresh"}).json()

    assert summary["inventory_rows"] == 1
    assert api.get("/api/v1/collection").json()["total"] == 0


def test_executing_without_reauth_is_401(api, monkeypatch):
    monkeypatch.setattr("app.security.verify_raw_token", lambda token: principal(ALICE))
    api.post("/api/v1/account/deletion", headers={"X-Reauth-Token": "fresh"})

    assert api.post("/api/v1/account/deletion/execute").status_code == 401


def test_executing_with_no_request_is_404(api, monkeypatch):
    monkeypatch.setattr("app.security.verify_raw_token", lambda token: principal(ALICE))
    assert api.post("/api/v1/account/deletion/execute",
                    headers={"X-Reauth-Token": "fresh"}).status_code == 404


def test_a_second_request_is_409(api, monkeypatch):
    monkeypatch.setattr("app.security.verify_raw_token", lambda token: principal(ALICE))
    api.post("/api/v1/account/deletion", headers={"X-Reauth-Token": "fresh"})

    assert api.post("/api/v1/account/deletion",
                    headers={"X-Reauth-Token": "fresh"}).status_code == 409
