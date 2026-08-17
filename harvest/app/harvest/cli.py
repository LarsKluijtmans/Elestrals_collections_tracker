"""Command-line entrypoint for the harvester. Run it from `harvest/`.

    python -m app.harvest --list                     what is registered, and its state
    python -m app.harvest --sync-sources             create missing rows, disabled
    python -m app.harvest --enable ebay_sold --note "..." --accepted-by "Lars Kluijtmans"
    python -m app.harvest --disable ebay_sold        the kill switch
    python -m app.harvest --source ebay_sold --mode deep
    python -m app.harvest --source ebay_sold --mode light
    python -m app.harvest --rollup                   recompute price_daily
    python -m app.harvest --sweep                    fail runs that died mid-scan

`--enable` requires **both** `--note` and `--accepted-by`, and there is no flag to skip either.
That is ADR-004 rather than ceremony: the decision accepted a contractual risk, and a risk
accepted by nobody in particular, on the basis of a review nobody wrote, is not an accepted risk.

Shares `HarvestRunner` with Celery and the admin API, so what an operator runs by hand is what
runs at 3am.
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy.exc import SQLAlchemyError

from ..config import settings
from ..core.db import SessionLocal
from ..core.dependencies import make_harvest_runner, make_rollup_service
from ..repositories.harvest_repository import HarvestRepository
from ..repositories.price_source_repository import (
    PriceSourceRepository, RiskAcceptanceRequired,
)
from .gate import SourceNotCleared
from .sources import UnknownSource, available_sources, describe_source


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.harvest",
        description="Collect Elestrals listings and prices.",
    )
    parser.add_argument("--source", help="registered source key")
    parser.add_argument("--mode", choices=("deep", "light"), default="light",
                        help="deep: the whole query space. light: known listings + neighbours")
    parser.add_argument("--list", action="store_true",
                        help="list registered sources with their configured state, then exit")
    parser.add_argument("--sync-sources", action="store_true",
                        help="create a disabled, note-less row for every registered connector")
    parser.add_argument("--enable", metavar="KEY",
                        help="enable a source (requires --note and --accepted-by)")
    parser.add_argument("--disable", metavar="KEY", help="disable a source")
    parser.add_argument("--note", help="what this source's terms actually say")
    parser.add_argument("--accepted-by", help="the person accepting the risk for this source")
    parser.add_argument("--rollup", action="store_true", help="recompute price_daily, then exit")
    parser.add_argument("--sweep", action="store_true",
                        help="sweep runs stuck in 'running' to 'failed', then exit")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    db = SessionLocal()
    try:
        sources = PriceSourceRepository(db)

        if args.list:
            return _list(sources)
        if args.sync_sources:
            return _sync(sources)
        if args.enable:
            return _enable(sources, args.enable, args.note, args.accepted_by)
        if args.disable:
            sources.disable(args.disable)
            print(f"{args.disable}: disabled. Takes effect on the next scan.")
            return 0
        if args.rollup:
            result = make_rollup_service(db).rebuild()
            print(f"rollup: {result.days} day(s), {result.rows} row(s), "
                  f"{result.excluded} point(s) excluded as outliers")
            return 0
        if args.sweep:
            swept = HarvestRepository(db).sweep_stale(
                older_than_minutes=settings.harvest_run_stale_after_minutes
            )
            print(f"swept {swept} stale run(s) to failed")
            return 0
        if not args.source:
            print("error: --source is required (or use --list)", file=sys.stderr)
            return 2

        return _run(db, args.source, args.mode)
    finally:
        db.close()


def _list(sources: PriceSourceRepository) -> int:
    # `--list` answers "what is registered and may it run?", and the first half is true without a
    # database. Someone checking which connectors exist on a machine with no MySQL should get the
    # list, not a stack trace.
    try:
        rows = {row.key: row for row in sources.list_all()}
    except SQLAlchemyError as exc:
        print(f"(database unavailable — configured state unknown: {type(exc).__name__})\n")
        rows = {}

    for key in available_sources():
        descriptor = describe_source(key)
        row = rows.get(key)
        sold = "REPORTS SALES" if descriptor.reports_sold else "asking prices only"
        print(f"{key}  ({descriptor.display_name})")
        print(f"    {descriptor.access_mode} · {descriptor.host} · {sold}")
        if row is None:
            print("    NO ROW — run --sync-sources")
        elif not row.enabled:
            print("    disabled")
        else:
            state = f"enabled, {row.rate_limit_per_min}/min"
            if row.quarantine_level:
                state += f", quarantine level {row.quarantine_level}"
            print(f"    {state}")
            print(f"    risk accepted by {row.risk_accepted_by} on {row.risk_accepted_on}")
        if row is not None and not (row.tos_review_note or "").strip():
            print("    no terms review note — cannot be enabled")

    for key in sorted(set(rows) - set(available_sources())):
        print(f"{key}  (no connector registered — orphaned config row)")
    return 0


def _sync(sources: PriceSourceRepository) -> int:
    for key in available_sources():
        descriptor = describe_source(key)
        row = sources.ensure(
            key,
            name=descriptor.display_name,
            base_url=f"https://{descriptor.host}",
            access_mode=descriptor.access_mode,
            reports_sold=descriptor.reports_sold,
        )
        print(f"{key}: {'exists' if row.enabled or row.tos_review_note else 'created (disabled)'}")
    return 0


def _enable(
    sources: PriceSourceRepository, key: str, note: str | None, accepted_by: str | None
) -> int:
    if not (note or "").strip() or not (accepted_by or "").strip():
        print(
            "error: --enable requires --note and --accepted-by.\n"
            "  --note        what this source's terms actually say, including whether they "
            "prohibit this\n"
            "  --accepted-by who is accepting that risk (ADR-004)",
            file=sys.stderr,
        )
        return 2
    if sources.by_key(key) is None:
        print(f"error: no source {key!r}. Run --sync-sources first.", file=sys.stderr)
        return 2
    try:
        sources.enable(key, note=note, accepted_by=accepted_by)
    except RiskAcceptanceRequired as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"{key}: enabled, risk accepted by {accepted_by}")
    return 0


def _run(db, source_key: str, mode: str) -> int:
    try:
        describe_source(source_key)
    except UnknownSource as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        run = make_harvest_runner(db).run(source_key=source_key, mode=mode, triggered_by="cli")
    except SourceNotCleared as exc:
        # Not a crash. The gate did its job, and the message says what to do next.
        print(f"refused: {exc}", file=sys.stderr)
        return 3

    print(
        f"run {run.id}  source={source_key} mode={mode} status={run.status}\n"
        f"  queries     {run.queries}\n"
        f"  fetched     {run.fetched}\n"
        f"  parsed      {run.parsed}\n"
        f"  accepted    {run.accepted}\n"
        f"  rejected    {run.rejected}\n"
        f"  discovered  {run.discovered}\n"
        f"  ended       {run.ended}"
    )
    if run.error_summary:
        print(f"\nerrors:\n{run.error_summary}", file=sys.stderr)
    return 0 if run.status == "success" else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
