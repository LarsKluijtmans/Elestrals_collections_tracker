"""Command-line entrypoint for `elestrals-api`'s scheduled work. Run it from `backend/`.

    python -m app.jobs --snapshot                 today's collection_snapshots row per user
    python -m app.jobs --snapshot --on 2026-03-03 back-fill a specific day
    python -m app.jobs --rebuild-completion SUB   regenerate one user's set_completion

**`--snapshot` is the one that has to run every night**, and the reason is unusual: nothing in
phase 1 reads what it writes. The counts for 3 March exist only if something wrote them on
3 March, so this is what makes phase 2's portfolio chart non-empty on the day it ships. Missing a
night leaves a permanent hole — `--on` exists to fill one, but only with today's collection, which
is why it is a repair tool and not a substitute.

Safe to run twice: `uq_collection_snapshot_user_day` makes a second run an update, and the update
deliberately leaves `total_value_cents` alone so a re-run cannot blank a day phase 2 has valued.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date

from sqlalchemy.exc import SQLAlchemyError

from ..core.db import SessionLocal
from ..models.base import utc_today
from ..core.dependencies import make_snapshot_service
from ..repositories.set_completion_repository import SetCompletionRepository
from ..repositories.set_repository import SetRepository
from ..services.completion_service import CompletionService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.jobs",
        description="Scheduled jobs for elestrals-api.",
    )
    parser.add_argument(
        "--snapshot", action="store_true",
        help="write today's collection_snapshots row for every user who holds anything",
    )
    parser.add_argument(
        "--on", metavar="YYYY-MM-DD",
        help="the day to record (default: today). Back-fills use the CURRENT collection, so this "
             "repairs a missed night — it does not reconstruct the past",
    )
    parser.add_argument(
        "--rebuild-completion", metavar="USER_SUB",
        help="regenerate one user's set_completion projection from inventory",
    )
    parser.add_argument(
        "--value-snapshots", action="store_true",
        help="write collection values onto snapshot rows, each using ITS OWN day's prices "
             "(story 022). Safe to re-run; leaves a day null when nothing priced it",
    )
    parser.add_argument(
        "--since", metavar="YYYY-MM-DD",
        help="with --value-snapshots: only value days from this date. Omit for every snapshot",
    )
    parser.add_argument(
        "--drain-outbox", action="store_true",
        help="attempt delivery for every pending notification that is due",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not (args.snapshot or args.rebuild_completion or args.value_snapshots
            or args.drain_outbox):
        print("error: nothing to do — pass --snapshot, --value-snapshots, --drain-outbox "
              "or --rebuild-completion", file=sys.stderr)
        return 2

    db = SessionLocal()
    try:
        if args.snapshot:
            return _snapshot(db, args.on)
        if args.value_snapshots:
            return _value_snapshots(db, args.since)
        if args.drain_outbox:
            return _drain_outbox(db)
        return _rebuild_completion(db, args.rebuild_completion)
    except SQLAlchemyError as exc:
        print(f"error: database unavailable: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


def _snapshot(db, on: str | None) -> int:
    taken_on = None
    if on:
        try:
            taken_on = date.fromisoformat(on)
        except ValueError:
            print(f"error: --on expects YYYY-MM-DD, got {on!r}", file=sys.stderr)
            return 2
        # UTC: the job stamps the snapshot with the UTC day, so a date that is merely
        # tomorrow *locally* is still a legitimate today.
        if taken_on > utc_today():
            # A snapshot dated tomorrow would sit at the end of every chart as a phantom point
            # nothing can ever correct.
            print("error: --on cannot be in the future", file=sys.stderr)
            return 2

    result = make_snapshot_service(db).take(taken_on=taken_on)
    print(
        f"snapshot {result.taken_on}: {result.users} user(s) — "
        f"{result.written} written, {result.updated} updated"
    )
    if result.users == 0:
        # Not an error. An install with no collections yet is a real state, and failing the cron
        # job for it would fill an inbox with alerts about nothing.
        print("  (no user holds anything yet)")
    return 0


def _value_snapshots(db, since: str | None) -> int:
    """Story 022. Runs *after* `--snapshot` on the same schedule: today's row must exist before
    it can be valued."""
    from ..repositories.inventory_repository import InventoryRepository
    from ..repositories.price_repository import PriceRepository
    from ..services.portfolio_service import PortfolioService

    start = None
    if since:
        try:
            start = date.fromisoformat(since)
        except ValueError:
            print(f"error: --since expects YYYY-MM-DD, got {since!r}", file=sys.stderr)
            return 2

    portfolio = PortfolioService(InventoryRepository(db), PriceRepository(db))
    valued, left_null = make_snapshot_service(db).value_days(
        portfolio, InventoryRepository(db), since=start,
    )
    print(f"valued {valued} snapshot day(s); {left_null} left null (no prices for that day)")
    if left_null and not valued:
        # Worth saying plainly rather than reporting a bare zero: the harvester not having reached
        # back that far is a different problem from the valuation being broken.
        print("  (no rollups cover these days yet — the chart starts where the prices start)")
    return 0


def _drain_outbox(db) -> int:
    from ..services.notification_service import NotificationService

    result = NotificationService(db).drain()
    print(
        f"outbox: {result.attempted} attempted, {result.sent} sent, "
        f"{result.retried} retried, {result.dead_lettered} dead-lettered"
    )
    # A dead letter is a notification nobody will ever receive. Non-zero exit so a cron wrapper
    # can surface it rather than it only existing in a log somebody has to think to read.
    return 1 if result.dead_lettered else 0


def _rebuild_completion(db, user_sub: str) -> int:
    completion = CompletionService(SetCompletionRepository(db), SetRepository(db))
    count = completion.rebuild_for_user(user_sub)
    db.commit()
    print(f"rebuilt completion for {user_sub}: {count} set(s)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
