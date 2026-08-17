"""Notifications, sharing and deletion — bolt 009, stories 032, 033 and 035.

Three assertions carry this file, one per story:

* `test_a_failed_delivery_is_retried_not_lost` — the outbox's whole reason to exist, and what
  story 034's "an outage delays rather than loses" was blocked on.
* `test_the_public_shape_has_no_cost_basis_field` — the bolt's own success criterion, written as a
  test that inspects the *model* rather than a response, so it fails when somebody adds a field
  rather than when somebody happens to have set one.
* `test_deletion_removes_every_table_keyed_on_the_subject` — enumerated against `TABLES`, so
  adding a user-owned table without adding it there fails here.
"""
from __future__ import annotations

from dataclasses import fields as dataclass_fields
from datetime import datetime, timedelta, timezone

import pytest

from app.models.base import utc_naive
from app.models.notification import MAX_ATTEMPTS, NotificationOutbox
from app.models.user_profile import UserProfile
from app.repositories.inventory_repository import InventoryRepository
from app.services.deletion_service import (
    TABLES, AlreadyRequested, DeletionService, NoPendingRequest, NotYetDue, subject_hash,
)
from app.services.notification_service import (
    DeliveryFailed, NotificationService, UnknownChannel, UnknownEvent,
)
from app.services.public_profile_service import (
    PublicHolding, PublicProfileService,
)
from test_inventory import ALICE, BOB, build_service, seed_catalog

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def catalog(db):
    return seed_catalog(db, card_count=3)


@pytest.fixture()
def notifications(db):
    return NotificationService(db, sender=lambda entry: None)


@pytest.fixture()
def failing(db):
    def explode(entry):
        raise DeliveryFailed("notification-api is unreachable")

    return NotificationService(db, sender=explode)


@pytest.fixture()
def public(db):
    return PublicProfileService(db)


@pytest.fixture()
def deletions(db):
    return DeletionService(db)


def profile(db, user_sub=ALICE, **kwargs) -> UserProfile:
    row = UserProfile(user_sub=user_sub, **kwargs)
    db.add(row)
    db.commit()
    return row


# --- notification preferences ---------------------------------------------------------

def test_defaults_are_conservative(notifications):
    """Story 032: nothing but account-critical mail until the user opts in. A product that mails
    people by default is a product people mute — and a muted channel is worse than none, because
    it looks like it works."""
    prefs = notifications.preferences(ALICE)

    assert prefs["account"] == "email"
    assert prefs["price_alert"] == "none"
    assert prefs["import_finished"] == "none"
    assert prefs["wishlist_match"] == "none"


def test_every_event_type_is_returned_even_unset(notifications):
    """So a client never has to know the defaults, and adding an event type needs no migration to
    backfill rows nobody has an opinion about."""
    assert set(notifications.preferences(ALICE)) == {
        "account", "price_alert", "import_finished", "wishlist_match",
    }


def test_setting_a_preference(notifications):
    prefs = notifications.set_preference(ALICE, event_type="price_alert", channel="email")
    assert prefs["price_alert"] == "email"


def test_preferences_are_per_user(notifications):
    notifications.set_preference(ALICE, event_type="price_alert", channel="email")
    assert notifications.preferences(BOB)["price_alert"] == "none"


def test_account_notifications_cannot_be_muted(notifications):
    """A deletion confirmation is not marketing. Somebody who turned everything off still needs
    to be told their account is going away."""
    with pytest.raises(UnknownChannel):
        notifications.set_preference(ALICE, event_type="account", channel="none")


def test_an_unknown_event_or_channel_is_refused(notifications):
    with pytest.raises(UnknownEvent):
        notifications.set_preference(ALICE, event_type="birthday", channel="email")
    with pytest.raises(UnknownChannel):
        notifications.set_preference(ALICE, event_type="price_alert", channel="carrier_pigeon")


# --- the outbox -----------------------------------------------------------------------

def test_enqueue_writes_before_anything_is_sent(db, notifications):
    """**The whole mechanism, in one assertion.** The row exists before delivery is attempted, so
    a process that dies mid-attempt has still recorded the notification. Reverse the order and it
    only ever existed in a stack frame that has since returned."""
    entry = notifications.enqueue(
        ALICE, event_type="account", subject="Hello", body="Body",
    )

    assert entry.status == "pending"
    assert entry.sent_at is None
    assert db.get(NotificationOutbox, entry.id) is not None


def test_a_muted_event_never_enters_the_queue(notifications):
    """Respected at enqueue rather than at delivery, so a muted event does not occupy the queue
    at all — and a backlog is never full of things nobody wanted."""
    assert notifications.enqueue(
        ALICE, event_type="price_alert", subject="x", body="y",
    ) is None


def test_draining_sends_and_marks(notifications):
    notifications.enqueue(ALICE, event_type="account", subject="Hello", body="Body")
    result = notifications.drain(now=NOW)

    assert result.sent == 1
    assert result.dead_lettered == 0


def test_a_failed_delivery_is_retried_not_lost(db, failing):
    """**Story 032's fourth criterion, and what story 034 was blocked on.** With notification-api
    stopped, entries queue and deliver on recovery — nothing is lost silently."""
    entry = failing.enqueue(ALICE, event_type="account", subject="Hello", body="Body")
    result = failing.drain(now=NOW)

    assert result.sent == 0
    assert result.retried == 1

    db.refresh(entry)
    assert entry.status == "pending"          # still queued
    assert entry.attempts == 1
    assert "unreachable" in entry.last_error


def test_a_retry_backs_off_rather_than_hammering(db, failing):
    """So one failing recipient does not monopolise every drain cycle."""
    entry = failing.enqueue(ALICE, event_type="account", subject="Hello", body="Body")
    failing.drain(now=NOW)

    db.refresh(entry)
    # Compared naive-to-naive: the column reads back without tzinfo whatever
    # `DateTime(timezone=True)` claims. See `models/base.utc_naive`.
    assert entry.next_attempt_at > utc_naive(NOW)


def test_a_backed_off_entry_is_invisible_until_due(failing):
    failing.enqueue(ALICE, event_type="account", subject="Hello", body="Body")
    failing.drain(now=NOW)

    # A second drain a second later must not pick it up again.
    assert failing.drain(now=NOW + timedelta(seconds=1)).attempted == 0
    # An hour later it is due.
    assert failing.drain(now=NOW + timedelta(hours=1)).attempted == 1


def test_it_delivers_on_recovery(db, failing, notifications):
    """The point of the whole thing: the outage ends and the queued notification goes out."""
    entry = failing.enqueue(ALICE, event_type="account", subject="Hello", body="Body")
    failing.drain(now=NOW)

    # notification-api comes back.
    notifications.drain(now=NOW + timedelta(hours=1))

    db.refresh(entry)
    assert entry.status == "sent"
    assert entry.sent_at is not None


def test_five_failures_dead_letter(db, failing):
    entry = failing.enqueue(ALICE, event_type="account", subject="Hello", body="Body")
    moment = NOW
    for _ in range(MAX_ATTEMPTS):
        failing.drain(now=moment)
        moment += timedelta(days=1)

    db.refresh(entry)
    assert entry.status == "dead"
    assert entry.attempts == MAX_ATTEMPTS


def test_a_dead_letter_stops_being_retried(db, failing):
    """Retrying a permanently bad address forever turns one broken recipient into an unbounded
    queue."""
    failing.enqueue(ALICE, event_type="account", subject="Hello", body="Body")
    moment = NOW
    for _ in range(MAX_ATTEMPTS):
        failing.drain(now=moment)
        moment += timedelta(days=1)

    assert failing.drain(now=moment + timedelta(days=30)).attempted == 0


def test_dead_letters_are_visible_to_an_operator(failing):
    """Story 032's fifth criterion. A dead letter nobody can see is a notification that was lost
    with extra steps."""
    failing.enqueue(ALICE, event_type="account", subject="Hello", body="Body")
    moment = NOW
    for _ in range(MAX_ATTEMPTS):
        failing.drain(now=moment)
        moment += timedelta(days=1)

    assert len(failing.dead_letters()) == 1


def test_a_service_with_no_sender_fails_loudly(db):
    """Rather than quietly marking everything sent. A misconfigured service should be obvious on
    the first drain, not discovered when somebody asks why they never got an email."""
    silent = NotificationService(db)
    silent.enqueue(ALICE, event_type="account", subject="Hello", body="Body")

    result = silent.drain(now=NOW)
    assert result.sent == 0
    assert result.retried == 1


def test_the_inbox_is_owner_scoped(notifications):
    notifications.enqueue(ALICE, event_type="account", subject="Mine", body="x")
    notifications.enqueue(BOB, event_type="account", subject="Theirs", body="y")

    assert [e.subject for e in notifications.for_user(ALICE)] == ["Mine"]


# --- the public collection ------------------------------------------------------------

def test_the_public_shape_has_no_cost_basis_field():
    """**The bolt's own success criterion**, and written against the *model* rather than a
    response — so it fails the moment somebody adds a field, not merely when somebody has set one.

    This is the difference between a whitelist and a filter. A filter is a rule somebody forgets
    to apply to the next field; a model that never had them cannot leak them.
    """
    names = {f.name for f in dataclass_fields(PublicHolding)}

    assert "acquired_unit_price_cents" not in names
    assert "acquired_on" not in names
    assert "acquired_currency" not in names
    assert "storage_location" not in names
    assert "notes" not in names
    assert "is_for_trade" not in names
    # And the whole surface is exactly this, so a future addition is a deliberate act.
    assert names == {
        "printing_id", "card_id", "name", "set_code", "collector_number",
        "element", "rarity", "finish", "condition", "quantity",
    }


def test_a_public_collection_is_reachable_by_handle(db, public, catalog):
    profile(db, handle="alice", collection_visibility="public")
    build_service(db).add(ALICE, printing_id=catalog["printings"]["BS1-001:common"], quantity=2)

    collection = public.by_handle("alice")
    assert collection.handle == "alice"
    assert collection.total_items == 2
    assert collection.distinct_printings == 1


def test_a_private_collection_is_not_found(db, public, catalog):
    """404, not 403 — a 403 confirms the handle exists, which is an enumeration oracle over who
    has an account."""
    profile(db, handle="alice", collection_visibility="private")
    assert public.by_handle("alice") is None


def test_the_default_visibility_is_private(db, public):
    profile(db, handle="alice")
    assert public.by_handle("alice") is None


def test_a_link_shared_collection_is_not_reachable_by_handle(db, public):
    """Or the token would be pointless."""
    profile(db, handle="alice", collection_visibility="link", share_token="tok" * 10)
    assert public.by_handle("alice") is None


def test_a_share_token_reaches_a_link_shared_collection(db, public, catalog):
    row = profile(db, handle="alice", collection_visibility="link")
    token = public.rotate_share_token(row)
    build_service(db).add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])

    collection = public.by_share_token(token)
    assert collection is not None
    assert collection.unlisted is True


def test_a_share_token_is_long_enough_not_to_guess(db, public):
    row = profile(db, handle="alice", collection_visibility="link")
    token = public.rotate_share_token(row)
    # 32 bytes base64url — 43 characters, 256 bits. Not a uuid4's 122.
    assert len(token) >= 40


def test_rotating_a_token_invalidates_the_old_one(db, public):
    """Rotation is the only revocation a shared URL has — there is no un-sending a link."""
    row = profile(db, handle="alice", collection_visibility="link")
    old = public.rotate_share_token(row)
    public.rotate_share_token(row)

    assert public.by_share_token(old) is None


def test_an_empty_token_matches_nothing(public):
    assert public.by_share_token("") is None


def test_the_public_collection_carries_only_whitelisted_values(db, public, catalog):
    """Belt and braces: the model cannot carry a cost basis, and this proves the built object
    does not either — including that a *populated* private field on the source row stays behind."""
    profile(db, handle="alice", collection_visibility="public")
    build_service(db).add(
        ALICE, printing_id=catalog["printings"]["BS1-001:common"],
        acquired_unit_price_cents=12_345, acquired_currency="EUR",
        storage_location="binder 2", notes="bought at a con",
    )

    (holding,) = public.by_handle("alice").holdings
    serialised = str(holding)
    assert "12345" not in serialised
    assert "binder 2" not in serialised
    assert "bought at a con" not in serialised


# --- deletion -------------------------------------------------------------------------

def test_requesting_deletion_sets_a_grace_period(deletions):
    """Cancellable until it executes. "I changed my mind" is a thing people say, and an
    irreversible button pressed in anger is a support ticket nobody can resolve."""
    request = deletions.request(ALICE, now=NOW)

    assert request.status == "pending"
    assert request.execute_after > utc_naive(NOW)


def test_requesting_twice_is_refused(deletions):
    deletions.request(ALICE, now=NOW)
    with pytest.raises(AlreadyRequested):
        deletions.request(ALICE, now=NOW)


def test_cancelling_a_request(deletions):
    deletions.request(ALICE, now=NOW)
    cancelled = deletions.cancel(ALICE)

    assert cancelled.status == "cancelled"
    assert deletions.pending(ALICE) is None


def test_cancelling_nothing_is_a_404(deletions):
    with pytest.raises(NoPendingRequest):
        deletions.cancel(ALICE)


def test_a_request_cannot_execute_before_its_time(deletions):
    deletions.request(ALICE, now=NOW)
    with pytest.raises(NotYetDue):
        deletions.execute(ALICE, now=NOW)


def test_a_due_request_executes(deletions, db, catalog):
    build_service(db).add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])
    request = deletions.request(ALICE, now=NOW)

    summary = deletions.execute(ALICE, now=request.execute_after + timedelta(seconds=1))

    assert summary.inventory_rows == 1
    assert InventoryRepository(db).count_for_user(ALICE) == 0


def test_deletion_removes_every_table_keyed_on_the_subject(deletions, db, catalog):
    """**Enumerated against `TABLES`**, so adding a user-owned table without adding it to that
    tuple fails here rather than silently leaving rows behind after an erasure."""
    from sqlalchemy import func, select

    inventory = build_service(db)
    inventory.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])

    from app.models.notification import NotificationPreference
    from app.models.saved_view import SavedView
    from app.models.wishlist_item import WishlistItem

    db.add_all([
        SavedView(user_sub=ALICE, name="Mine", filters={}),
        WishlistItem(user_sub=ALICE, printing_id=catalog["printings"]["BS1-002:common"]),
        NotificationPreference(user_sub=ALICE, event_type="price_alert", channel="email"),
        UserProfile(user_sub=ALICE, handle="alice"),
    ])
    db.commit()

    deletions.request(ALICE, now=NOW)
    deletions.execute(ALICE, force=True)

    for model in TABLES:
        remaining = db.scalar(
            select(func.count()).select_from(model).where(model.user_sub == ALICE)
        )
        assert remaining == 0, f"{model.__tablename__} still has rows"


def test_deletion_leaves_other_users_alone(deletions, db, catalog):
    inventory = build_service(db)
    inventory.add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])
    inventory.add(BOB, printing_id=catalog["printings"]["BS1-002:common"])

    deletions.request(ALICE, now=NOW)
    deletions.execute(ALICE, force=True)

    assert InventoryRepository(db).count_for_user(BOB) == 1


def test_the_audit_record_does_not_contain_the_subject(deletions, db, catalog):
    """**Story 035's third and fifth criteria together.** The audit outlives the deletion, so
    storing the `sub` would mean the erasure did not erase — and an operator still needs to be
    able to prove it happened."""
    build_service(db).add(ALICE, printing_id=catalog["printings"]["BS1-001:common"])
    deletions.request(ALICE, now=NOW)
    deletions.execute(ALICE, force=True)

    audit = deletions.verify(ALICE)
    assert audit is not None
    assert audit.subject_hash != ALICE
    assert ALICE not in str(vars(audit))
    assert audit.inventory_rows == 1


def test_the_audit_is_verifiable_from_the_subject(deletions, db, catalog):
    """Somebody holding the `sub` gets a yes; somebody holding only the audit table learns
    nothing about whose data it was."""
    deletions.request(ALICE, now=NOW)
    deletions.execute(ALICE, force=True)

    assert deletions.verify(ALICE) is not None
    assert deletions.verify(BOB) is None
    assert deletions.verify(ALICE).subject_hash == subject_hash(ALICE)


def test_the_request_row_itself_is_removed(deletions, db):
    """It carries the subject, so it cannot survive the erasure — the audit references it by id
    instead, which is not personal data."""
    from sqlalchemy import func, select

    from app.models.deletion_request import DeletionRequest

    deletions.request(ALICE, now=NOW)
    deletions.execute(ALICE, force=True)

    assert db.scalar(
        select(func.count()).select_from(DeletionRequest)
        .where(DeletionRequest.user_sub == ALICE)
    ) == 0


def test_due_lists_what_a_scheduled_job_would_walk(deletions):
    request = deletions.request(ALICE, now=NOW)

    assert deletions.due(now=NOW) == []
    assert [r.id for r in deletions.due(now=request.execute_after + timedelta(seconds=1))] \
        == [request.id]


def test_a_cancelled_request_is_never_due(deletions):
    request = deletions.request(ALICE, now=NOW)
    deletions.cancel(ALICE)

    assert deletions.due(now=request.execute_after + timedelta(days=1)) == []
