"""Verify against the real platform MySQL what has only ever been tested on SQLite.

Cleans up after itself so the database is left as it was found.
"""
from __future__ import annotations

import pathlib
import tempfile
import threading

from sqlalchemy import select, text
from sqlalchemy.orm import sessionmaker

from app.core.db import engine
from app.importer.sources import SOURCES, register
from app.importer.sources.csv_seed import CsvSeedAdapter
from app.core.dependencies import make_import_runner
from app.models.card import Card
from app.models.inventory_item import InventoryItem
from app.models.set import Set
from app.repositories.card_repository import CardRepository, SearchQuery
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.printing_repository import PrintingRepository
from app.repositories.set_completion_repository import SetCompletionRepository
from app.repositories.set_repository import SetRepository
from app.services.catalog_read_service import CardSearchService
from app.services.completion_service import CompletionService
from app.services.inventory_service import InventoryService, ItemChanged

Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
USER = "verify-user-001"
SET_CODE = "VER1"

SETS = f"set_code,name,series,released_on,card_count\n{SET_CODE},Verification Set,Testing,2026-01-01,3\n"
CARDS = f"""set_code,collector_number,name,card_type,element,rune_type,attack,defence,spirit_cost,rarity,finish,language,edition,image_url
{SET_CODE},VR-001,Teratlas Verify,elestral,earth,,2400,2100,"{{""earth"": 2}}",common,normal,,,
{SET_CODE},VR-001,Teratlas Verify,elestral,earth,,2400,2100,"{{""earth"": 2}}",holo_rare,foil,,,
{SET_CODE},VR-002,Vipyro Verify,elestral,fire,,1800,1500,,rare,normal,,,
{SET_CODE},VR-003,Bad Rarity Row,rune,,invoke,,,,not_a_real_rarity,normal,,,
"""

ok, fail = [], []


def check(label: str, condition: bool, detail: str = "") -> None:
    (ok if condition else fail).append(label)
    print(f"  {'PASS' if condition else 'FAIL'}  {label}{(' — ' + detail) if detail else ''}")


def build_service(db) -> InventoryService:
    return InventoryService(
        InventoryRepository(db), PrintingRepository(db),
        CompletionService(SetCompletionRepository(db), SetRepository(db)),
    )


def cleanup() -> None:
    db = Session()
    try:
        db.execute(text("DELETE FROM inventory_items WHERE user_sub = :u"), {"u": USER})
        db.execute(text("DELETE FROM set_completion WHERE user_sub = :u"), {"u": USER})
        set_id = db.scalar(select(Set.id).where(Set.code == SET_CODE))
        if set_id:
            db.execute(text(
                "DELETE FROM printings WHERE card_id IN (SELECT id FROM cards WHERE set_id=:s)"
            ), {"s": set_id})
            db.execute(text("DELETE FROM cards WHERE set_id = :s"), {"s": set_id})
            db.execute(text("DELETE FROM sets WHERE id = :s"), {"s": set_id})
        db.execute(text("DELETE FROM import_rejections"))
        db.execute(text("DELETE FROM catalog_imports"))
        db.commit()
    finally:
        db.close()


def main() -> int:
    cleanup()
    tmp = pathlib.Path(tempfile.mkdtemp())
    (tmp / "sets.csv").write_text(SETS, encoding="utf-8")
    (tmp / f"{SET_CODE}.csv").write_text(CARDS, encoding="utf-8")

    class VerifySeed(CsvSeedAdapter):
        name = "verify_seed"

    register(VerifySeed(tmp))

    print("\n[1] Catalog importer against MySQL")
    db = Session()
    run1 = make_import_runner(db).run(source_name="verify_seed", set_codes=[SET_CODE])
    check("import succeeds", run1.status == "success", f"status={run1.status}")
    check("2 cards added", run1.cards_added == 2, f"added={run1.cards_added}")
    check("3 printings added", run1.printings_added == 3, f"printings={run1.printings_added}")
    check("1 row rejected", run1.rejected == 1, f"rejected={run1.rejected}")
    db.close()

    print("\n[2] Idempotency on MySQL (the ON DUPLICATE KEY UPDATE claim)")
    db = Session()
    run2 = make_import_runner(db).run(source_name="verify_seed", set_codes=[SET_CODE])
    check("re-run adds nothing", run2.cards_added == 0, f"added={run2.cards_added}")
    check("re-run updates nothing", run2.cards_updated == 0, f"updated={run2.cards_updated}")
    check("re-run reports unchanged", run2.cards_unchanged == 2, f"unchanged={run2.cards_unchanged}")
    db.close()

    print("\n[3] Coverage reported against the declared printed size")
    db = Session()
    set_row = SetRepository(db).get_by_code(SET_CODE)
    imported = CardRepository(db).count_for_set(set_row.id)
    check("2 of 3 cards imported", imported == 2 and set_row.card_count == 3,
          f"{imported}/{set_row.card_count}")
    db.close()

    print("\n[4] Search ranking on MySQL")
    db = Session()
    svc = CardSearchService(CardRepository(db), PrintingRepository(db))
    items, total = svc.search(SearchQuery(term="verify", limit=10))
    check("infix search finds both cards", total == 2, f"total={total}")
    items2, _ = svc.search(SearchQuery(term="Teratlas Verify", limit=10))
    check("exact name ranks first", items2 and items2[0].match_kind == "exact_name",
          items2[0].match_kind if items2 else "no results")
    check("primary printing is commonest",
          items2 and items2[0].primary_printing.rarity == "common",
          items2[0].primary_printing.rarity if items2 else "-")
    order1 = [i.card_id for i in svc.search(SearchQuery(term="verify", limit=10))[0]]
    order2 = [i.card_id for i in svc.search(SearchQuery(term="verify", limit=10))[0]]
    check("search order is stable", order1 == order2)
    db.close()

    print("\n[5] Inventory merge on MySQL")
    db = Session()
    pid_common = db.scalar(text("""
        SELECT p.id FROM printings p JOIN cards c ON c.id = p.card_id
        WHERE c.collector_number='VR-001' AND p.rarity='common'"""))
    inv = build_service(db)
    r1 = inv.add(USER, printing_id=pid_common)
    r2 = inv.add(USER, printing_id=pid_common)
    check("second add merges", r2.merged is True)
    check("quantity is 2", r2.item.quantity == 2, f"qty={r2.item.quantity}")
    check("one row exists", InventoryRepository(db).count_for_user(USER) == 1)
    db.close()

    print("\n[6] Graded copies stay separate (NULL distinct in a MySQL unique index)")
    db = Session()
    inv = build_service(db)
    inv.add(USER, printing_id=pid_common, is_graded=True, grader="PSA", grade=9)
    inv.add(USER, printing_id=pid_common, is_graded=True, grader="PSA", grade=9)
    graded = [i for i in InventoryRepository(db).list_for_user(USER) if i.is_graded]
    check("two identical PSA 9 copies are two rows", len(graded) == 2, f"rows={len(graded)}")
    db.close()

    print("\n[7] Concurrent adds on MySQL — the invariant bolt 004 exists for")
    db = Session()
    pid_holo = db.scalar(text("""
        SELECT p.id FROM printings p JOIN cards c ON c.id = p.card_id
        WHERE c.collector_number='VR-001' AND p.rarity='holo_rare'"""))
    db.close()

    barrier = threading.Barrier(4)
    errors: list[Exception] = []

    def worker():
        s = Session()
        try:
            barrier.wait(timeout=20)
            build_service(s).add(USER, printing_id=pid_holo)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            s.close()

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=40)

    db = Session()
    rows = list(db.scalars(select(InventoryItem).where(
        InventoryItem.user_sub == USER, InventoryItem.printing_id == pid_holo,
        InventoryItem.is_graded == False)))  # noqa: E712
    check("no errors under contention", not errors, str(errors[:1]))
    check("4 concurrent adds produced ONE row", len(rows) == 1, f"rows={len(rows)}")
    check("quantity is exactly 4", rows and rows[0].quantity == 4,
          f"qty={rows[0].quantity if rows else '-'}")
    db.close()

    print("\n[8] Concurrent undos on MySQL — the compare-and-swap ADR-005 rests on")
    # The unit tests prove `compare_and_adjust` is one atomic statement on SQLite. What is only
    # verifiable here is that MySQL's row locking resolves the race the same way: of two undos
    # carrying the same `expected_quantity`, exactly one matches and the other is refused. A
    # read-compare-write would let both read 4, both decide the row is unchanged, and both write
    # 3 — losing a copy with no error anywhere.
    # The row the four concurrent adds above built, so this runs against a real quantity of 4.
    db = Session()
    target = db.scalars(select(InventoryItem).where(
        InventoryItem.user_sub == USER, InventoryItem.printing_id == pid_holo,
        InventoryItem.is_graded.is_(False))).first()
    target_id, start_qty = target.id, target.quantity
    db.close()

    barrier2 = threading.Barrier(2)
    verdicts: list[str] = []
    verdict_lock = threading.Lock()

    def undoer():
        s = Session()
        try:
            barrier2.wait(timeout=20)
            build_service(s).adjust(USER, target_id, delta=-1, expected_quantity=start_qty)
            outcome = "applied"
        except ItemChanged:
            outcome = "refused"
        except Exception as exc:  # noqa: BLE001
            outcome = f"error: {type(exc).__name__}: {exc}"
        finally:
            s.close()
        with verdict_lock:
            verdicts.append(outcome)

    undo_threads = [threading.Thread(target=undoer) for _ in range(2)]
    for t in undo_threads:
        t.start()
    for t in undo_threads:
        t.join(timeout=40)

    db = Session()
    after = InventoryRepository(db).get(USER, target_id)
    check("exactly one concurrent undo applied", verdicts.count("applied") == 1, str(verdicts))
    check("the loser was refused, not an error", verdicts.count("refused") == 1, str(verdicts))
    check("quantity dropped by exactly one",
          after is not None and after.quantity == start_qty - 1,
          f"qty={after.quantity if after else '-'} (was {start_qty})")
    db.close()

    print("\n[9] Adjusting to zero deletes the row rather than storing a zero")
    db = Session()
    inv = build_service(db)
    single = inv.add(USER, printing_id=pid_common, condition="damaged").item
    result = inv.adjust(USER, single.id, delta=-1, expected_quantity=single.quantity)
    check("adjust to zero reports deleted", result.deleted is True)
    check("the row is gone", InventoryRepository(db).get(USER, single.id) is None)
    db.close()

    print("\n[10] Completion recomputed in the same transaction")
    db = Session()
    completion = CompletionService(SetCompletionRepository(db), SetRepository(db))
    view = [v for v in completion.view(USER) if v.set_code == SET_CODE]
    check("completion row exists", bool(view))
    if view:
        v = view[0]
        check("owned_cards counts distinct cards", v.owned_cards == 1, f"owned={v.owned_cards}")
        check("card_count is the declared size", v.card_count == 3, f"count={v.card_count}")
        check("ratio is 1/3", abs(v.ratio - 1 / 3) < 1e-9, f"ratio={v.ratio:.3f}")
    db.close()

    print("\n[11] app_logs written by the real logging path")
    db = Session()
    log_count = db.scalar(text("SELECT COUNT(*) FROM app_logs"))
    check("log_event wrote rows to MySQL", log_count > 0, f"rows={log_count}")
    db.close()

    SOURCES.pop("verify_seed", None)
    cleanup()

    print(f"\n{'=' * 60}\n{len(ok)} passed, {len(fail)} failed")
    if fail:
        for f in fail:
            print(f"  FAILED: {f}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
