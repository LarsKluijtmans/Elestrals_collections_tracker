---
intent: 001-collection-tracker
phase: inception
status: bolts-planned
updated: 2026-08-09T12:00:00Z
---

# Collection Tracker - Bolt Plan

**9 bolts, 36 stories, 7 units.** Eight DDD bolts and one simple bolt.

## Bolt sequence

| # | Bolt | Unit | Stories | Type | Complexity | Uncertainty |
|---|---|---|---|---|---|---|
| 1 | `001-platform-foundation` | 001 | 6 | DDD | 2 | 1 |
| 2 | `002-card-catalog-schema-import` | 002 | 3 | DDD | 3 | **3** |
| 3 | `003-card-catalog-surface` | 002 | 4 | DDD | 2 | 1 |
| 4 | `004-inventory-core` | 003 | 4 | DDD | 3 | 1 |
| 5 | `005-collection-entry` | 004 | 3 | DDD | 3 | 2 |
| 6 | `006-collection-browse` | 004 | 6 | DDD | 3 | 2 |
| 7 | `007-sealed-and-wishlist` | 005 | 2 | simple | 1 | 1 |
| 8 | `008-import-export` | 006 | 3 | DDD | 3 | 2 |
| 9 | `009-profile-and-sharing` | 007 | 5 | DDD | 2 | 1 |

## Dependency graph

```text
001-platform-foundation
   └─> 002-card-catalog-schema-import
          ├─> 003-card-catalog-surface ──┐
          └─> 004-inventory-core ────────┼─> 005-collection-entry ─> 006-collection-browse
                     │                   │
                     ├───────────────────┘
                     ├─> 007-sealed-and-wishlist ─> 008-import-export
                     └─> 009-profile-and-sharing
```

After bolt 004, three chains are independent: the collection experience (005 → 006), the
sealed/import chain (007 → 008), and profile (009). With one pair of hands they run in the order
above; with more, they parallelise cleanly.

## Milestones

| After bolt | The product can… | Worth showing to |
|---|---|---|
| 001 | be signed into, themed, and observed | nobody yet — but every later bolt starts from working |
| 002 | answer "does the catalog exist and is it correct" | yourself — this is the go/no-go on the whole intent |
| 003 | be browsed by anyone as a card database | a friend |
| 004 | record ownership (via API) | nobody — no UI yet |
| **005** | **have a real collection entered into it** | **a real collector, for the timing test** |
| **006** | **be used daily** | **first external users** |
| 007 | track sealed and wants | same users, more completely |
| 008 | absorb an existing spreadsheet collection | users who already track elsewhere — the biggest adoption unlock |
| 009 | be shared, and left | public launch |

**Bolt 006 is the minimum shippable product.** 007–009 are each independently valuable and could be
reordered by demand — if early users all arrive with spreadsheets, promote 008 above 007.

## Risk-driven ordering

Two ordering choices are deliberate and should not be "optimised" away:

1. **Catalog before inventory (002 before 004).** Inventory is more central, but the catalog is
   where this intent can *fail*. Bolt 002 opens with a one-day spike on real source data. If public
   Elestrals data is unusable, that must be known in week one — not after an inventory UI has been
   built on the assumption.

2. **Entry before browsing (005 before 006).** Browsing an empty collection proves nothing. The
   moment entry works there is real data, and the 5-second / 10-minute targets become measurable
   with a real person rather than estimated.

## Where the schedule can give

In order of what to cut first under pressure:

1. `026-wishlist` (Should) — the product works without it
2. `033-public-collection` (Could) — the only `Could` in the intent
3. `021-saved-views` (Should) — filters still work, they just have to be rebuilt
4. `018-undo-recent-adds` (Should) — but only if 016's timing target is already met without it

Nothing marked `Must` is negotiable, and `008-catalog-importer` and `013-add-inventory-item` are the
two stories where cutting corners costs the most later — one silently corrupts the catalog, the
other silently loses rows under concurrency.
