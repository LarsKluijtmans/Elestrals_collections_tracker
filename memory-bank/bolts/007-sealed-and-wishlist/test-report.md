---
bolt: 007-sealed-and-wishlist
stage: test
status: complete
created: 2026-08-17T20:40:00Z
---

# Test Report: 007-sealed-and-wishlist

**Status: `complete`.** Every criterion met. This is the smallest bolt in the intent and it is the
only one so far that closes without an asterisk.

## Automated

```
backend → pytest -q      378 passed   (was 337; +41)
frontend → tsc --noEmit  clean
frontend → vite build    clean
```

`test_sealed_and_wishlist.py`, 41 tests: 14 for sealed inventory, 13 for the wishlist, 14 over HTTP
including **one cross-user test per endpoint** — the rule bolt 004 set and every user-owned surface
since has inherited.

## The two refusals this bolt is built around

Both are things the code deliberately does not do, and both would be easy and wrong.

**Opening a box creates no singles.** `test_opening_creates_no_singles` asserts the inventory count
stays at zero. A box has an expected distribution and an actual pull, and they are never the same —
so generated cards would be wrong *every single time*, and wrong in a way the collector has to find
and undo one row at a time, having first noticed their collection contains cards they never owned.
The bolt notes call this out and the UI states it where the button is, rather than burying it.

**Acquiring a wished printing does not clear the wish.** `acquired_but_still_wished` reports the
overlap; nothing removes anything. A collector may want a playset, or a better condition, or a first
edition of something they own unlimited. Deleting stated intent because a row appeared elsewhere
destroys information they cannot recover and never agreed to lose.

## Why sealed is its own table

Story 025's third criterion — sealed holdings appear in neither `/collection` nor any completion
figure — is guaranteed structurally rather than by discipline. A `kind` column on `inventory_items`
would have put the burden on every future query remembering to exclude sealed, and the one that
forgets counts a booster box as a card. `test_sealed_never_appears_in_the_collection_table` and
`test_sealed_never_touches_completion` assert it from both sides.

`is_sealed` is part of the unique key, so a sealed box and an opened one stay separate holdings.
That falls out of the constraint rather than out of a service remembering to branch — the same shape
as `merge_condition` in bolt 004, one case simpler because there is no NULL here.

## A bug the tests caught

`WishlistService.edit` validated the merged state with `fields.desired_quantity or item.desired_quantity`.
**`0 or x` is `x`**, so a patch setting the quantity to zero fell through to the stored value,
validated *that*, and handed the zero to the database — where `ck_wishlist_quantity_positive`
rejected it as an `IntegrityError` rather than as a 400 with a sentence.

The classic falsy-zero mistake, and worth noting that the CHECK constraint is what turned a silent
bad write into a loud bad error. Fixed with `is not None`; pinned by
`test_editing_validates_the_merged_state_not_the_patch`.

## Money is never half-set

`max_price_cents` and `max_price_currency` are both-or-neither, at the service *and* in a CHECK
constraint. A maximum of "500" is meaningless without knowing the currency, and story 026 rejects a
bare number outright. Three tests cover it: amount alone, currency alone, and the pair.

Notably, the edit path validates the **merged** state rather than the patch — clearing only the
currency would otherwise leave an amount behind, which is half a price and looks like a real one.

## Notes

The bolt notes suggested this was the place to absorb schedule pressure, since the wishlist is a
`Should` and the product is usable without it. That did not turn out to be necessary; it is a small
bolt because the domain modelling was genuinely done in bolt 004, which is exactly what
`simple-construction-bolt` is for.

`wishlist_items.max_price_cents` is the threshold phase 2's price alerts will fire on. The schema
anticipates that and nothing here builds it.
