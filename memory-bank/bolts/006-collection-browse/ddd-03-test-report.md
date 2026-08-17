---
bolt: 006-collection-browse
stage: test
status: partial
created: 2026-08-17T20:10:00Z
---

# Test Report: 006-collection-browse

**Status: `partial`, on measurement rather than behaviour.** Every functional criterion is built and
tested. The two that are not met are both numbers nobody has put on a clock — the 60fps scroll and
the 400ms p95 — plus the screen-reader pass this project has now deferred twice.

## Automated

```
backend   → pytest -q          337 passed   (was 202; +135)
frontend  → vitest run         176 passed   (was 130; +46)
frontend  → tsc --noEmit       clean
frontend  → vite build         clean
```

| Suite | Tests | Covers |
|---|---|---|
| `test_collection_filters.py` | 26 | the filter vocabulary, and the **round trip** saved views depend on |
| `test_collection_browse.py` | 31 | keyset paging, sorting, filtering, missing-cards |
| `test_bulk_actions.py` | 17 | selection-as-filter, partial success, cross-user isolation |
| `test_snapshots_and_dashboard.py` | 16 | the nightly snapshot's idempotency, the value tile's refusal |
| `test_collection_api.py` | 37 | all nine endpoints, one cross-user test each |
| `test_jobs_cli.py` | 8 | `python -m app.jobs --snapshot`, the only thing that runs the job |
| `filters.test.ts` | 23 | URL serialisation, both directions |
| `csv.test.ts` | 16 | escaping, and the column order that *is* the import contract |
| `QuantityStepper.test.tsx` | 13 | debounce, optimism, reconciliation |

### Coverage

| Module | |
|---|---|
| `bulk_service.py` | 100% |
| `collection_browse_service.py` | 100% |
| `snapshot_service.py` | 100% |
| `dashboard_service.py` | 98% |
| `collection_filters.py` | 97% |
| `controllers/collection.py` | 91% |
| `saved_view_service.py` | 87% |
| **This bolt's backend total** | **95%** |

## The assertions that carry this bolt

**`test_a_row_inserted_while_paging_does_not_shift_the_page`.** Every other paging test here passes
against an offset cursor. Offsets fail exactly where this product lives — a collector adds cards
*while* scrolling — and they fail silently: page 2 repeats a row, or skips one. Neither looks like an
error. It looks like the table lost a card, which is the worst thing this product can do. Its mirror,
`..._deleted_...does_not_skip_one`, covers the more dangerous direction, where the row is never seen
at all.

**`test_rows_sharing_a_timestamp_still_page_totally`.** Without the `id` tie-break the sort is not a
total order, and two rows created in the same millisecond can straddle a page boundary so that one is
never returned. The fast-add flow produces same-millisecond rows by design, so this is the normal
case rather than a contrived one.

**`test_the_dashboard_ring_agrees_with_the_missing_view`.** Story 024's last criterion, asserted
across the two surfaces that would otherwise disagree — both count distinct *cards* over the declared
printed size. Two definitions of "missing" is how a completed set shows as incomplete on one page and
complete on another.

**`test_re_running_does_not_erase_a_value_phase_two_wrote`.** The one that would silently destroy
data. Phase 2's nightly valuation fills `total_value_cents` on the same `collection_snapshots` rows
the phase-1 counter writes. A counter that overwrote the whole row would blank every valued day the
following night, and nothing would report it.

## A bug the tests caught

The quantity stepper fired a request for a burst that **netted to zero**. Click `+`, notice the
mis-click, click `−`: the debounce timer sees a final value different from the previous *displayed*
one and sends it, writing "set it to what it already is". Harmless in effect, wrong in principle, and
it puts a pointless entry in whatever eventually audits this table.

Fixed by comparing the debounced value against the *server's* value rather than the previous shown
one — the same rule the grid's delta coalescer already applies to a click followed by a shift-click.
Caught by `a burst up and back down cancels out to no request`.

A second, cheaper one: three controllers built response models with `vars(dataclass)`, which returns
nothing useful for a `slots=True` dataclass — they have no `__dict__` at all. Five API tests failed
at once on it. `asdict` throughout.

## Not verified

| Criterion | Why |
|---|---|
| 10,000 rows at 60fps | Needs a browser, a real collection and a frame profiler. The windowing, the fixed per-density row heights and `ix_inventory_user_created_id` are all in place; none of them is a measurement |
| List API p95 < 400ms | `scripts/bench.py` measures import, search and write. A browse benchmark is a natural addition and is not there |
| Screen reader | `aria-sort` on sortable headers, `aria-pressed` on filter chips, named steppers and a live result count are asserted in tests. An actual NVDA/VoiceOver pass is not — the **same gap bolt 003 carries**, now on two bolts |
| WCAG 2.2 AA in full | Contrast, focus visibility and an axe run remain unrun across the whole app |

## Notes

`FilterSet` is deliberately the only definition of what a filter *means*, shared by the query string,
`saved_views.filters` and — when story 033 lands — a valuation slice. Story 033 explains why in one
sentence worth keeping: two implementations over one data model will disagree, and the disagreement
surfaces as a valuation that does not match the item list on screen, which reads to a collector as
the valuation being broken.

`collection_snapshots` is now written nightly by `python -m app.jobs --snapshot`. Nothing in phase 1
reads it. That is the point, and it is why it went unbuilt long enough for three phase-2 stories to
be marked `blocked` on it.
