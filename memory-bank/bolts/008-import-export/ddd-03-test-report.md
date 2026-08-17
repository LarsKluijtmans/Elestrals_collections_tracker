---
bolt: 008-import-export
stage: test
status: partial
created: 2026-08-17T21:25:00Z
---

# Test Report: 008-import-export

**Status: `partial`, on two unmeasured budgets.** Every behavioural criterion is met. The 30-second
dry run and the 100MB export have the right *shapes* — a generator, an index built once per job —
and neither has been put on a clock.

## Automated

```
backend  → pytest -q       476 passed   (was 378; +98)
frontend → tsc --noEmit    clean
frontend → vite build      clean
```

| Module | Coverage |
|---|---|
| `controllers/import_export.py` | 100% |
| `import_parser.py` | 99% |
| `import_service.py` | 95% |
| `import_matcher.py` | 94% |
| `export_service.py` | 88% |
| **This bolt's total** | **96%** |

## The bug the tests caught, and it was the bolt's central criterion

**The commit was not atomic.** Story 029's second criterion is that one bad row on line 900 leaves
nothing written, and `test_one_bad_row_writes_nothing_at_all` failed with `assert 2 == 0`.

The cause is worth writing down because it is a consequence of a *good* earlier decision.
`InventoryService` commits each write together with its completion recompute — deliberately, and it
is the reason completion can never disagree with inventory. Story 029 also requires imports to write
**through** that service, so imported rows obey the same invariants as hand-entered ones. Both rules
are right, and together they made the import commit-per-row: the rollback after a failure rolled
back only the uncommitted tail, and 899 rows stayed.

The fix is an explicit `InventoryService.atomic()` context manager that suspends per-write commits
so a caller can own the transaction. Recomputes still run per write, so the projection is correct at
the moment the caller commits; only the commit waits. The single-row path is untouched.

Worth noting how this was found: not by reading the code, but by an assertion that deliberately made
row 3 of 3 explode and then counted the rows in the database. A test that only checked the *error*
would have passed.

## A second, smaller one

`normalise_name` replaced every non-alphanumeric with a space, so `"Vipyro's Ember"` became
`"vipyro s ember"` and `"Vipyros Ember"` became `"vipyros ember"` — the same card typed by two
people, differing by a whole token, which is exactly the gap that pushes a real match below the
similarity floor. Apostrophes are now removed rather than spaced.

## The round trip

`test_export_then_import_is_a_no_op` is the strongest check this bolt has, and the reason the bolt
notes say to build export first: it turns rung 1 of the matching ladder from a claim into something
provable. Export a collection, import the file back, and the diff is 0 adds, 0 rejects, every row
matched on `exact_printing`.

Two variants pin the edges. The same file imported by a *different* user is still 0 rejects but 3
adds — proving the matcher matches the catalog while the verdict describes the collection. And a
card called `Atlas, "Reborn"` round-trips intact, which is the escaping failure that would otherwise
shift every later column by one and import as something else entirely: a silently wrong import
rather than a failed one.

## The ladder, and the line it holds

| Rung | Tested |
|---|---|
| 1 `exact_printing` | matches; a **stale** id falls through to lower rungs rather than rejecting |
| 2 `natural_key` | matches, case-insensitively |
| 3 `set_and_number` | matches when unambiguous; **rejects when not** |
| 4 `fuzzy_name` | matches above the floor, always `needs_confirmation` |
| 5 `none` | rejects, and the reason names what was tried |

`test_below_the_floor_is_a_rejection_not_a_low_confidence_match` is the one the bolt notes told us
to hold under schedule pressure. A confident wrong match silently corrupts a collection somebody has
kept for years, and they will not find out until they go looking for a card they no longer appear to
own. An honest failure costs one row of manual work.

`test_ambiguity_is_a_rejection_not_a_coin_flip` is the same principle one rung up: a card with a
normal and a foil printing, and nothing in the file to tell them apart, is a *question*.

## Formula injection

Five tests. `=`, `+`, `-`, `@` and the leading-tab and leading-CR variants are all prefixed with `'`.

The attack is on the *user*, not on us — a crafted note becomes a formula when they open the file,
and `=IMPORTXML(...)` can exfiltrate the rest of their sheet. `test_a_note_from_the_database_is_defused_too`
makes the point that this runs on our **own** export: the dangerous string arrived through a note
field somebody typed, and it is dangerous on the way out.

## Real spreadsheets

The fixtures are the specific, recurring ways collector files are messy: UTF-8 with a BOM, CP1252
from Excel on Windows, semicolon delimiters, quoted commas, short rows, and blank rows in the middle.

Two are worth calling out. **Encoding order is not alphabetical**: `utf-8-sig` first so a BOM is
consumed rather than left on the first header — where it would make `printing_id` fail to match its
own alias and silently break round-tripping of our own export — and CP1252 last because it *cannot*
fail, so trying it early turns real UTF-8 into mojibake without raising. And the delimiter is counted
on the **header line** rather than by `csv.Sniffer`, which guesses from a sample and is confidently
wrong on a file whose card names contain semicolons.

## Not verified

| Criterion | Why |
|---|---|
| 5,000-row dry run < 30s | Needs a realistic catalog and a clock. The matcher's name index is built once per job rather than per row, which is what makes the budget reachable — but that is a design property, not a measurement |
| 10,000-row export under 100MB RSS | Export is a generator and the route streams it; asserted structurally (`test_export_streams_rather_than_accumulating`) rather than by watching memory |
| `inventory.bulk_imported` metering | Story 029's sixth criterion. Not wired — usage metering is off across the whole service until the M2M scopes are granted, which is bolt 001's open item |

## Notes

`import_jobs`/`import_rows` are named at a deliberate distance from `catalog_imports`. That table is
*our catalog* being imported from a data source; these are *a user's collection* from their own
spreadsheet. Same word, nothing else in common — and conflating them would put user-uploaded content
in a table the operator console reads.

`python-multipart` is now a dependency. FastAPI needs it for `UploadFile` and raises at **import**
time rather than on first request, so a missing wheel takes down the whole service rather than one
endpoint. It is in `requirements.txt` with that note attached.
