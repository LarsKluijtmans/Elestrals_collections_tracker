"""Command-line entrypoint for the catalog importer.

    python -m app.importer --list
    python -m app.importer --source csv_seed --set FE01
    python -m app.importer --source csv_seed              # every declared set

Shares `ImportRunner` with the admin endpoint, so there is one execution path rather than two
that drift. Run it from `backend/`.
"""
from __future__ import annotations

import argparse
import sys

from ..core.db import SessionLocal
from ..core.dependencies import make_import_runner
from .sources import UnknownSource, available_sources, get_source


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.importer",
                                     description="Import the Elestrals card catalog.")
    parser.add_argument("--source", default="csv_seed", help="registered source name")
    parser.add_argument("--set", dest="sets", action="append",
                        help="set code; repeatable. Omit for every declared set.")
    parser.add_argument("--list", action="store_true",
                        help="list registered sources and available sets, then exit")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list:
        for name in available_sources():
            adapter = get_source(name)
            descriptor = adapter.describe()
            network = "network" if descriptor.requires_network else "offline"
            print(f"{name}  ({descriptor.display_name}, {network})")
            try:
                print(f"    sets: {', '.join(adapter.available_sets()) or '(none declared)'}")
            except Exception as exc:  # noqa: BLE001 — listing must not crash on a bad seed
                print(f"    sets: unavailable — {exc}")
        return 0

    try:
        get_source(args.source)
    except UnknownSource as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    db = SessionLocal()
    try:
        runner = make_import_runner(db)
        run = runner.run(source_name=args.source, set_codes=args.sets)
    finally:
        db.close()

    print(
        f"run {run.id}  status={run.status}\n"
        f"  sets seen        {run.sets_seen}\n"
        f"  cards added      {run.cards_added}\n"
        f"  cards updated    {run.cards_updated}\n"
        f"  cards unchanged  {run.cards_unchanged}\n"
        f"  printings added  {run.printings_added}\n"
        f"  rejected         {run.rejected}"
    )
    if run.error_summary:
        print(f"\nerrors:\n{run.error_summary}", file=sys.stderr)

    return 0 if run.status == "success" else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
