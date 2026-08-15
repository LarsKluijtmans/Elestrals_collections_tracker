# Curated catalog seed

Phase 1's source of truth for the card catalog. The decision to hand-compile rather than
import from a live source is recorded in
`memory-bank/bolts/002-card-catalog-schema-import/adr-001-catalog-data-source.md`: the
publisher's Terms of Use prohibit scraping, prohibit accessing their site to build a competing
product, and prohibit reproducing site content.

**Compile these files from cards you own and from publicly published checklists. Do not scrape
`collect.elestrals.com`.**

## Files

| File | Contents |
|---|---|
| `sets.csv` | one row per set. `card_count` is the **printed** set size |
| `{SET_CODE}.csv` | one row per **printing**; card-level fields repeat across a card's rows |

Lines beginning with `#` are ignored, so you can leave notes in place.

## Why `card_count` lives in `sets.csv` and not in the card file

It is the completion denominator. If it were counted from the rows actually imported, an
incomplete catalog would report 100% completion — a wrong answer that looks right. Declaring it
separately is what lets the importer say "126 declared, 40 imported" instead of "40 of 40".

That mismatch is reported as a `warning` in `app_logs` and on the run-detail API response. A
newly declared set with no card file yet is therefore *expected* to report 0/126 — that is the
guard working, not a bug.

## Columns in `{SET_CODE}.csv`

| Column | Required | Notes |
|---|---|---|
| `collector_number` | yes | e.g. `BS1-001`. Identifies the card within the set |
| `name` | yes | |
| `card_type` | yes | `elestral` \| `spirit` \| `rune` |
| `rarity` | yes | `common`, `uncommon`, `rare`, `holo_rare`, `full_art`, `alt_art`, `prismatic`, `secret`, `promo` |
| `finish` | no | `normal` (default), `foil`, `reverse_foil`, `prismatic` |
| `language` | no | BCP-47, default `en` |
| `edition` | no | `first` \| `unlimited`. Defaults to `first` for `FE*` sets |
| `element` | for elestral/spirit | one of the eight elements |
| `rune_type` | for rune | `invoke`, `counter`, `artifact`, `stadium`, `divine` |
| `attack`, `defence` | elestral only | integers |
| `spirit_cost` | no | JSON object, e.g. `"{""earth"":2}"` |
| `subtype`, `rules_text`, `flavour_text`, `artist` | no | |
| `image_url` | no | a URL only — we never store image bytes |
| `is_tracked_for_price` | no | `false` to stop phase 2 pricing this SKU |

## Rules the importer enforces

- **A card is imported whole or not at all.** One bad row rejects that card's every printing,
  because a card missing a printing silently corrupts set completion.
- **Unknown vocabulary is rejected, never defaulted.** An unrecognised rarity is not quietly
  turned into `common` — a wrong rarity is a wrong SKU, a wrong price and a wrong count.
- **Rows of one card must agree** on every card-level field. Disagreement rejects the card
  rather than letting file ordering decide which value wins.
- **Re-running changes nothing.** Rows whose content is unchanged issue no SQL at all.

## Usage

```bash
cd backend
python -m app.importer --list
python -m app.importer --source csv_seed --set FE01
```
