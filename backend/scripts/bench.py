"""Measure the NFR targets that have only ever been estimates.

  bolt 002  full re-import < 15 minutes
  bolt 003  search p95 < 150ms with the full catalog loaded
  bolt 004  inventory write p95 < 200ms including recompute; recompute < 50ms
  bolt 005  /adjust p95 < 200ms - the undo path, which the add benchmark does not cover
  bolt 006  collection list p95 < 400ms at 10,000 holdings
  bolt 008  5,000-row dry run < 30s; 10,000-row export streams under 100MB RSS

Seeds a synthetic catalog at the size unit-brief.md projects (~5,000 cards), measures, and
removes it again.
"""
from __future__ import annotations

import pathlib
import random
import statistics
import tempfile
import time

from sqlalchemy import select, text
from sqlalchemy.orm import sessionmaker

from app.core.db import engine
from app.core.dependencies import make_import_runner
from app.importer.sources import SOURCES, register
from app.importer.sources.csv_seed import CsvSeedAdapter
from app.models.printing import Printing
from app.models.set import Set
from app.repositories.card_repository import CardRepository, SearchQuery
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.printing_repository import PrintingRepository
from app.repositories.set_completion_repository import SetCompletionRepository
from app.repositories.set_repository import SetRepository
from app.services.catalog_read_service import CardSearchService
from app.services.collection_browse_service import CollectionBrowseService
from app.services.collection_filters import FilterSet
from app.services.completion_service import CompletionService
from app.services.export_service import ExportService
from app.services.import_service import ImportService
from app.services.inventory_service import InventoryService

Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
USER = "bench-user-001"
SETS_N, CARDS_PER_SET = 10, 500          # 5,000 cards
ELEMENTS = ["fire", "water", "wind", "earth", "thunder", "frost", "solar", "lunar"]
SYLLABLES = ["ter", "atlas", "vip", "yro", "nok", "sar", "mel", "dra", "kor", "eth", "lun", "pyx"]

random.seed(7)


def p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, int(len(ordered) * 0.95) - 1)]


def report(label: str, samples: list[float], budget_ms: float) -> bool:
    med, p, mx = statistics.median(samples), p95(samples), max(samples)
    passed = p < budget_ms
    print(f"  {'PASS' if passed else 'FAIL'}  {label}")
    print(f"        median {med:7.1f}ms   p95 {p:7.1f}ms   max {mx:7.1f}ms   budget {budget_ms:.0f}ms  n={len(samples)}")
    return passed


def _rss_mb() -> float | None:
    """Resident set size in MB, or **None when it cannot be measured on this platform**.

    `None` rather than `0.0`, and the distinction is the whole reason this docstring exists. The
    first version returned 0 on failure, so on Windows the export check compared `0 - 0 < 100`,
    printed PASS, and had measured nothing at all. That is the exact failure this repo has now
    recorded twice - `status-integrity.cjs` skipping CRLF files, and bolt 013's route enumeration
    scanning an empty list. A benchmark that passes by measuring nothing is worse than one that
    fails.

    POSIX gets `resource`; Windows gets the Win32 call, because that is where this is actually run.
    """
    import sys

    try:
        import resource  # noqa: PLC0415 - POSIX only

        maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Linux reports ru_maxrss in kilobytes, macOS in bytes. Same field, different unit, and
        # getting it wrong is a factor of 1024 in a number compared against a 100MB budget.
        return maxrss / 1024 / 1024 if sys.platform == "darwin" else maxrss / 1024
    except ImportError:
        pass

    try:  # Windows
        import ctypes
        from ctypes import wintypes

        class _Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        kernel32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
        # The argtypes are not decoration. `GetCurrentProcess` returns the pseudo-handle
        # `(HANDLE)-1`; without a declared restype ctypes treats it as a 32-bit int, and the
        # callee reads 64 bits of which the upper half is whatever was on the stack. The call
        # then returns 0 and the measurement is silently lost - which is how the first version
        # of this ended up reporting `RSS 0 -> 0MB` and passing.
        kernel32.GetCurrentProcess.argtypes = []
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(_Counters), wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

        counters = _Counters()
        counters.cb = ctypes.sizeof(_Counters)
        if psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        ):
            return counters.WorkingSetSize / 1024 / 1024
    except Exception:  # noqa: BLE001 - any failure means "cannot measure", which is the point
        pass

    return None


def _seed_holdings(db, *, target: int) -> None:
    """Top the bench user's collection up to `target` rows, fast.

    Bulk-inserted rather than driven through `InventoryService`: the service is what benchmark [C]
    measures, and paying its per-row recompute 10,000 times here would spend ten minutes building
    a fixture for a benchmark about reading.
    """
    import uuid
    from datetime import datetime, timedelta, timezone

    from app.models.inventory_item import InventoryItem

    have = InventoryRepository(db).count_for_user(USER)
    if have >= target:
        return

    printing_ids = list(db.scalars(select(Printing.id)))
    owned = {
        (i.printing_id, i.merge_condition)
        for i in InventoryRepository(db).list_for_user(USER, limit=target * 2)
    }
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    conditions = ["near_mint", "lightly_played", "mint", "damaged"]

    # (printing, condition) pairs, not printings. The catalog is 7,500 printings and the target is
    # 10,000 holdings, so iterating printings alone caps the seed below the size story 019 names -
    # and a benchmark at 7,500 quietly reported as one at 10,000 is a measurement of the wrong
    # thing. `uq_inventory_merge` is over (user, printing, merge_condition), so the same printing
    # in two conditions is two legitimate rows, which is exactly how a real collection looks.
    rows, n = [], 0
    for condition in conditions:
        for pid in printing_ids:
            if have + len(rows) >= target:
                break
            if (pid, condition) in owned:
                continue
            rows.append({
                "id": str(uuid.uuid4()), "user_sub": USER, "printing_id": pid,
                "condition": condition, "quantity": 1 + (n % 4), "is_graded": False,
                "grader": None, "grade": None, "merge_condition": condition,
                "acquired_on": None, "acquired_unit_price_cents": None,
                "acquired_currency": None, "storage_location": None, "notes": None,
                "is_for_trade": False,
                # Staggered, so the keyset cursor has a real ordering to page through rather
                # than 10,000 rows sharing a timestamp and falling back to the id tie-break.
                "created_at": base + timedelta(seconds=n),
                "updated_at": base + timedelta(seconds=n),
            })
            n += 1
        if have + len(rows) >= target:
            break

    if rows:
        db.execute(InventoryItem.__table__.insert(), rows)
        db.commit()
    print(f"        (seeded to {InventoryRepository(db).count_for_user(USER):,} holdings)")


def _export_bytes(rows) -> bytes:
    return "".join(ExportService().singles(rows)).encode("utf-8")


def cleanup(codes: list[str]) -> None:
    db = Session()
    try:
        db.execute(text("DELETE FROM inventory_items WHERE user_sub=:u"), {"u": USER})
        db.execute(text("DELETE FROM set_completion WHERE user_sub=:u"), {"u": USER})
        for code in codes:
            sid = db.scalar(select(Set.id).where(Set.code == code))
            if sid:
                db.execute(text(
                    "DELETE FROM printings WHERE card_id IN (SELECT id FROM cards WHERE set_id=:s)"
                ), {"s": sid})
                db.execute(text("DELETE FROM cards WHERE set_id=:s"), {"s": sid})
                db.execute(text("DELETE FROM sets WHERE id=:s"), {"s": sid})
        db.execute(text("DELETE FROM import_rejections"))
        db.execute(text("DELETE FROM catalog_imports"))
        db.commit()
    finally:
        db.close()


def main() -> int:
    codes = [f"BN{i:02d}" for i in range(SETS_N)]
    cleanup(codes)

    tmp = pathlib.Path(tempfile.mkdtemp())
    (tmp / "sets.csv").write_text(
        "set_code,name,series,released_on,card_count\n"
        + "".join(f"{c},Bench {c},Bench,2026-01-0{(i % 9) + 1},{CARDS_PER_SET}\n"
                 for i, c in enumerate(codes)),
        encoding="utf-8",
    )

    header = ("set_code,collector_number,name,card_type,element,rune_type,attack,defence,"
              "spirit_cost,rarity,finish,language,edition,image_url\n")
    for code in codes:
        rows = [header]
        for n in range(1, CARDS_PER_SET + 1):
            name = "".join(random.choice(SYLLABLES) for _ in range(3)).capitalize()
            el = random.choice(ELEMENTS)
            rows.append(f"{code},{code}-{n:03d},{name},elestral,{el},,1000,900,,common,normal,,,\n")
            if n % 2 == 0:  # ~1.5 printings per card
                rows.append(f"{code},{code}-{n:03d},{name},elestral,{el},,1000,900,,holo_rare,foil,,,\n")
        (tmp / f"{code}.csv").write_text("".join(rows), encoding="utf-8")

    class BenchSeed(CsvSeedAdapter):
        name = "bench_seed"

    register(BenchSeed(tmp))
    results = []
    skipped: list[str] = []

    print(f"\n[A] Full import of {SETS_N * CARDS_PER_SET} cards  (budget: 15 min)")
    db = Session()
    t0 = time.perf_counter()
    run = make_import_runner(db).run(source_name="bench_seed", set_codes=codes)
    import_s = time.perf_counter() - t0
    db.close()
    ok_import = import_s < 900 and run.status == "success"
    print(f"  {'PASS' if ok_import else 'FAIL'}  imported {run.cards_added} cards / "
          f"{run.printings_added} printings in {import_s:.1f}s")
    results.append(ok_import)

    print("\n[A2] Idempotent re-import (0 added, 0 updated)")
    db = Session()
    t0 = time.perf_counter()
    run2 = make_import_runner(db).run(source_name="bench_seed", set_codes=codes)
    reimport_s = time.perf_counter() - t0
    db.close()
    ok_re = run2.cards_added == 0 and run2.cards_updated == 0
    print(f"  {'PASS' if ok_re else 'FAIL'}  re-import {reimport_s:.1f}s  "
          f"added={run2.cards_added} updated={run2.cards_updated} unchanged={run2.cards_unchanged}")
    results.append(ok_re)

    print("\n[B] Search p95  (budget: 150ms, 3-character prefix)")
    db = Session()
    search = CardSearchService(CardRepository(db), PrintingRepository(db))
    terms = [s[:3] for s in SYLLABLES] * 10
    for t in terms[:10]:
        search.search(SearchQuery(term=t, limit=25))          # warm
    samples = []
    for t in terms:
        t0 = time.perf_counter()
        search.search(SearchQuery(term=t, limit=25))
        samples.append((time.perf_counter() - t0) * 1000)
    results.append(report("3-char prefix search", samples, 150))
    db.close()

    print("\n[C] Inventory write p95, including completion recompute  (budget: 200ms)")
    db = Session()
    printing_ids = list(db.scalars(select(Printing.id).limit(300)))
    inv = InventoryService(
        InventoryRepository(db), PrintingRepository(db),
        CompletionService(SetCompletionRepository(db), SetRepository(db)),
    )
    samples = []
    for pid in printing_ids[:200]:
        t0 = time.perf_counter()
        inv.add(USER, printing_id=pid)
        samples.append((time.perf_counter() - t0) * 1000)
    results.append(report("add incl. recompute", samples, 200))
    db.close()

    print("\n[D] Completion recompute alone  (budget: 50ms)")
    db = Session()
    completion = CompletionService(SetCompletionRepository(db), SetRepository(db))
    set_ids = list(db.scalars(select(Set.id).where(Set.code.in_(codes))))
    samples = []
    for _ in range(100):
        sid = random.choice(set_ids)
        t0 = time.perf_counter()
        completion.recompute(USER, [sid])
        samples.append((time.perf_counter() - t0) * 1000)
    db.commit()
    results.append(report("recompute one set", samples, 50))
    db.close()

    print("\n[E] Adjust p95 - the undo path  (budget: 200ms)")
    # Bolt 005 listed this as unmeasured: bench.py measured the ADD path, not this one, and
    # /adjust does more work - a compare-and-swap plus the same completion recompute.
    db = Session()
    inv = InventoryService(
        InventoryRepository(db), PrintingRepository(db),
        CompletionService(SetCompletionRepository(db), SetRepository(db)),
    )
    items = InventoryRepository(db).list_for_user(USER, limit=200)
    samples = []
    for item in items[:150]:
        t0 = time.perf_counter()
        inv.adjust(USER, item.id, delta=1, expected_quantity=item.quantity)
        samples.append((time.perf_counter() - t0) * 1000)
    results.append(report("adjust incl. recompute", samples, 200))
    db.close()

    print("\n[F] Collection list p95 at 10,000 holdings  (budget: 400ms)")
    # The scale story 019 targets. Seeded to 10,000 rather than measured at 200, because the
    # question is whether the keyset index holds at the size the story names - a page-one query
    # over 200 rows passes on any implementation, including the offset one this replaced.
    db = Session()
    _seed_holdings(db, target=10_000)
    browse = CollectionBrowseService(
        InventoryRepository(db), CardRepository(db), SetRepository(db)
    )
    empty = FilterSet.from_params({})
    filtered = FilterSet.from_params({"condition": ["near_mint"]})

    samples = []
    for _ in range(30):
        t0 = time.perf_counter()
        browse.page(USER, empty, limit=50)
        samples.append((time.perf_counter() - t0) * 1000)
    results.append(report("unfiltered page 1", samples, 400))

    # Deep into the set, where an OFFSET implementation degrades and a keyset one does not.
    cursor = None
    for _ in range(20):
        page = browse.page(USER, empty, limit=50, cursor=cursor)
        cursor = page.next_cursor
        if cursor is None:
            break
    samples = []
    for _ in range(30):
        t0 = time.perf_counter()
        browse.page(USER, empty, limit=50, cursor=cursor)
        samples.append((time.perf_counter() - t0) * 1000)
    results.append(report("page ~1000 deep (keyset)", samples, 400))

    samples = []
    for _ in range(30):
        t0 = time.perf_counter()
        browse.page(USER, filtered, limit=50)
        samples.append((time.perf_counter() - t0) * 1000)
    results.append(report("filtered page 1 (joins catalog)", samples, 400))
    db.close()

    print("\n[G] CSV export of 10,000 rows  (budget: streams, < 100MB RSS)")
    db = Session()
    rows = InventoryRepository(db).list_for_user(USER, limit=10_000)
    before = _rss_mb()
    t0 = time.perf_counter()
    written = 0
    for line in ExportService().singles(rows):
        # Consumed and discarded, exactly as StreamingResponse does. Accumulating here would
        # measure the benchmark's own list rather than the exporter's memory.
        written += len(line)
    seconds = time.perf_counter() - t0
    peak = _rss_mb()

    if before is None or peak is None:
        # Reported, not silently passed. See `_rss_mb`.
        print(f"  SKIP  export {len(rows)} rows - RSS is not readable on this platform")
        print(f"        {written / 1024 / 1024:.1f}MB written in {seconds:.1f}s   "
              f"(the streaming shape is asserted by a unit test; the budget is not measured here)")
        skipped.append("10,000-row export under 100MB RSS")
    else:
        growth = peak - before
        ok_export = growth < 100
        print(f"  {'PASS' if ok_export else 'FAIL'}  export {len(rows)} rows")
        print(f"        {written / 1024 / 1024:.1f}MB written in {seconds:.1f}s   "
              f"RSS {before:.0f} -> {peak:.0f}MB (+{growth:.0f}MB, budget +100MB)")
        results.append(ok_export)
    db.close()

    print("\n[H] CSV import dry run, 5,000 rows  (budget: 30s)")
    db = Session()
    csv_bytes = _export_bytes(InventoryRepository(db).list_for_user(USER, limit=5_000))
    importer = ImportService(db, InventoryService(
        InventoryRepository(db), PrintingRepository(db),
        CompletionService(SetCompletionRepository(db), SetRepository(db)),
    ))
    t0 = time.perf_counter()
    job = importer.start(USER, filename="bench.csv", raw=csv_bytes)
    seconds = time.perf_counter() - t0
    ok_dry = seconds < 30
    print(f"  {'PASS' if ok_dry else 'FAIL'}  dry run {job.total_rows} rows")
    print(f"        {seconds:.1f}s   budget 30s   "
          f"({job.add_count} add, {job.update_count} update, {job.rejected_count} rejected)")
    results.append(ok_dry)
    # The round trip at scale: every row should match its own printing_id on rung 1.
    rung1 = sum(1 for r in job.rows if r.match_rung == "exact_printing")
    print(f"        rung-1 matches: {rung1}/{len(job.rows)}")
    importer.delete(USER, job.id)
    db.close()

    SOURCES.pop("bench_seed", None)
    cleanup(codes)

    print(f"\n{'=' * 62}\n{sum(results)}/{len(results)} targets met")
    for name in skipped:
        # Named individually. "11/11 met" with an unmeasurable check silently counted as a
        # pass is the number that gets quoted later as if it meant something.
        print(f"  NOT MEASURED: {name}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
