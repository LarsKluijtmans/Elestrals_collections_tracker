"""Measure the NFR targets that have only ever been estimates.

  bolt 002  full re-import < 15 minutes
  bolt 003  search p95 < 150ms with the full catalog loaded
  bolt 004  inventory write p95 < 200ms including recompute; recompute < 50ms

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
from app.services.completion_service import CompletionService
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

    SOURCES.pop("bench_seed", None)
    cleanup(codes)

    print(f"\n{'=' * 62}\n{sum(results)}/{len(results)} targets met")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
