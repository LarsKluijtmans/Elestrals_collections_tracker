---
created: 2026-08-09T12:00:00Z
updated: 2026-08-09T12:00:00Z
---

# Data Model — database `elestrals`

All tables live in our own MySQL database. Money is stored as **integer minor units**
(`*_cents BIGINT`) with an explicit ISO-4217 `currency CHAR(3)` — never a float, never an implied
currency. All timestamps are `DATETIME(6)` in UTC.

## The central modelling decision: Card vs Printing

A collector does not own "Vipyro". They own *a specific physical object*: Vipyro, Base Set, Holo
Rare, 1st Edition, English, in Near Mint condition. Prices attach to that object, not to the name.

So the catalog is three levels, and **`printings` is the SKU** — the thing inventory, prices and
listings all point at:

```
sets ──< cards ──< printings
                      ▲
                      ├── inventory_items   (+ condition)
                      ├── price_observations (+ condition)
                      ├── wishlist_items
                      └── listings          (+ condition)
```

Getting this wrong is the single most expensive mistake available here — every later feature
(valuation, completion, listings) is a query over `printings`. It is settled at inception on purpose.

---

## Catalog (read-mostly, globally shared)

### `sets`
| Column | Type | Notes |
|---|---|---|
| `id` | `CHAR(36)` PK | |
| `code` | `VARCHAR(16)` UNIQUE | e.g. `BASE`, `MOON` |
| `name` | `VARCHAR(128)` | |
| `series` | `VARCHAR(64)` NULL | grouping above set |
| `released_on` | `DATE` NULL | |
| `card_count` | `INT` | printed set size, used as the completion denominator |
| `logo_asset_url` | `VARCHAR(512)` NULL | |
| `created_at` / `updated_at` | `DATETIME(6)` | |

### `cards`
| Column | Type | Notes |
|---|---|---|
| `id` | `CHAR(36)` PK | |
| `set_id` | FK → `sets.id` | |
| `collector_number` | `VARCHAR(16)` | unique within set |
| `name` | `VARCHAR(160)` | |
| `card_type` | `ENUM('elestral','spirit','rune')` | the three Elestrals card types |
| `element` | `ENUM('fire','water','wind','earth','thunder','frost','solar','lunar')` NULL | Elestrals and Spirits; NULL for most Runes |
| `rune_type` | `ENUM('invoke','counter','artifact','stadium','divine')` NULL | Runes only |
| `subtype` | `VARCHAR(64)` NULL | e.g. creature family |
| `attack` / `defence` | `INT` NULL | Elestrals only |
| `spirit_cost` | `JSON` NULL | `{"fire": 2, "wind": 1}` |
| `rules_text` | `TEXT` NULL | |
| `flavour_text` | `TEXT` NULL | |
| `artist` | `VARCHAR(128)` NULL | |
| `created_at` / `updated_at` | `DATETIME(6)` | |

UNIQUE `(set_id, collector_number)`. INDEX on `name` (prefix search), `(card_type, element)`.

### `printings` — **the SKU**
| Column | Type | Notes |
|---|---|---|
| `id` | `CHAR(36)` PK | |
| `card_id` | FK → `cards.id` | |
| `rarity` | `ENUM('common','uncommon','rare','holo_rare','full_art','alt_art','prismatic','secret','promo')` | |
| `finish` | `ENUM('normal','foil','reverse_foil','prismatic')` | |
| `language` | `CHAR(5)` | BCP-47, default `en` |
| `edition` | `ENUM('unlimited','first')` | |
| `image_url` | `VARCHAR(512)` NULL | see the image-rights note below |
| `is_tracked_for_price` | `BOOL` DEFAULT 1 | lets us stop scraping dead SKUs |
| `created_at` / `updated_at` | `DATETIME(6)` | |

UNIQUE `(card_id, rarity, finish, language, edition)`.

> **Image rights.** We store a URL, never bytes, until we have written permission from the rights
> holder. If permission is obtained, images move to storage-api with an immutable object key.

### `sealed_products`
| Column | Type | Notes |
|---|---|---|
| `id` | `CHAR(36)` PK | |
| `set_id` | FK → `sets.id` NULL | NULL for cross-set bundles |
| `kind` | `ENUM('booster_pack','booster_box','starter_deck','elite_box','bundle','case','other')` | |
| `name` | `VARCHAR(160)` | |
| `contents_note` | `VARCHAR(255)` NULL | e.g. "24 packs × 11 cards" |
| `image_url` | `VARCHAR(512)` NULL | |
| `is_tracked_for_price` | `BOOL` DEFAULT 1 | |

### `catalog_imports`
Run log for the importer: `id`, `source`, `started_at`, `finished_at`, `status`
(`running|success|partial|failed`), `sets_seen`, `cards_added`, `cards_updated`, `printings_added`,
`rejected`, `error_summary TEXT`.

---

## Identity & profile

### `user_profiles`
Keyed on the JWT subject. Holds **only** what the platform has no opinion on.

| Column | Type | Notes |
|---|---|---|
| `user_sub` | `CHAR(36)` PK | JWT `sub` — never client-supplied |
| `handle` | `VARCHAR(32)` UNIQUE NULL | public name, needed from phase 3 |
| `collection_visibility` | `ENUM('private','link','public')` DEFAULT `'private'` | |
| `default_currency` | `CHAR(3)` DEFAULT `'EUR'` | |
| `condition_scale` | `ENUM('tcg','cardmarket')` DEFAULT `'tcg'` | grading vocabulary preference |
| `created_at` / `updated_at` | `DATETIME(6)` | |

No email, no display name, no avatar — those are enriched from auth-api on read.

---

## Inventory (phase 1)

### `inventory_items`
| Column | Type | Notes |
|---|---|---|
| `id` | `CHAR(36)` PK | |
| `user_sub` | `CHAR(36)` | **every query filters on this** |
| `printing_id` | FK → `printings.id` | |
| `condition` | `ENUM('mint','near_mint','lightly_played','moderately_played','heavily_played','damaged')` | |
| `quantity` | `INT UNSIGNED` CHECK > 0 | |
| `is_graded` | `BOOL` DEFAULT 0 | |
| `grader` / `grade` | `VARCHAR(16)` / `DECIMAL(3,1)` NULL | e.g. `PSA` / `9.5` |
| `acquired_on` | `DATE` NULL | |
| `acquired_unit_price_cents` | `BIGINT` NULL | cost basis, drives phase-2 P/L |
| `acquired_currency` | `CHAR(3)` NULL | |
| `storage_location` | `VARCHAR(64)` NULL | "binder 2, page 7" |
| `notes` | `VARCHAR(512)` NULL | |
| `is_for_trade` | `BOOL` DEFAULT 0 | seeds phase-3 listings |
| `created_at` / `updated_at` | `DATETIME(6)` | |

UNIQUE `(user_sub, printing_id, condition, is_graded, grader, grade)` for the ungraded common case —
adding a duplicate increments `quantity` rather than creating a row. Graded copies are individually
meaningful, so they are exempt from the merge (enforced in the service, not the constraint).

INDEX `(user_sub, printing_id)`, `(user_sub, created_at)`.

### `sealed_inventory_items`
Same shape against `sealed_products`: `user_sub`, `sealed_product_id`, `quantity`, `is_sealed BOOL`,
`acquired_on`, `acquired_unit_price_cents`, `acquired_currency`, `storage_location`, `notes`.

### `wishlist_items`
`id`, `user_sub`, `printing_id`, `desired_quantity`, `max_price_cents` NULL, `priority ENUM('low','normal','high')`, `created_at`.
UNIQUE `(user_sub, printing_id)`.

### `collection_snapshots` (written from phase 1, *read* from phase 2)
A nightly row per user so portfolio-over-time has history from day one rather than starting the day
phase 2 ships. Cheap insurance.

`id`, `user_sub`, `taken_on DATE`, `item_count`, `distinct_printings`, `total_value_cents` NULL,
`currency`, `valuation_confidence ENUM('none','low','medium','high')`.
UNIQUE `(user_sub, taken_on)`.

---

## Pricing (phase 2)

### `price_sources`
| Column | Type | Notes |
|---|---|---|
| `id` | `CHAR(36)` PK | |
| `key` | `VARCHAR(32)` UNIQUE | `ebay`, `tcgplayer`, … |
| `name` | `VARCHAR(128)` | |
| `base_url` | `VARCHAR(255)` | |
| `access_mode` | `ENUM('official_api','feed','scrape')` | |
| `enabled` | `BOOL` | kill switch, no deploy needed |
| `robots_checked_on` | `DATE` NULL | |
| `tos_review_note` | `TEXT` NULL | **must be filled before `enabled = 1`** |
| `rate_limit_per_min` | `INT` | |
| `weight` | `DECIMAL(3,2)` | influence on the blended median |

### `scrape_runs`
`id`, `source_id`, `started_at`, `finished_at`, `status`, `fetched`, `parsed`, `accepted`,
`rejected`, `error_summary`. One row per run, inserted **before** work starts.

### `price_observations` — the raw fact table
| Column | Type | Notes |
|---|---|---|
| `id` | `BIGINT` PK AUTO | high volume |
| `source_id` | FK → `price_sources.id` | |
| `run_id` | FK → `scrape_runs.id` | provenance for every row |
| `printing_id` | FK → `printings.id` NULL | NULL if it matched a sealed product |
| `sealed_product_id` | FK → `sealed_products.id` NULL | exactly one of the two is set |
| `condition` | same enum as inventory, NULL if unstated | |
| `sale_type` | `ENUM('sold','listed')` | **`sold` is the truth; `listed` is an asking price** |
| `observed_at` | `DATETIME(6)` | when the sale happened, not when we scraped it |
| `price_cents` / `currency` | `BIGINT` / `CHAR(3)` | |
| `shipping_cents` | `BIGINT` NULL | |
| `quantity` | `INT` DEFAULT 1 | |
| `external_id` | `VARCHAR(128)` | dedupe key within a source |
| `source_url` | `VARCHAR(512)` | auditable back to origin |
| `match_confidence` | `DECIMAL(3,2)` | how sure the title-matcher is |

UNIQUE `(source_id, external_id)` — re-running a scrape never double-counts.
INDEX `(printing_id, observed_at)`, `(sealed_product_id, observed_at)`.

### `price_daily` — the rollup everything reads
Charts and valuation never scan the fact table.

`printing_id` / `sealed_product_id`, `condition`, `day DATE`, `currency`, `low_cents`,
`median_cents`, `high_cents`, `mean_cents`, `observation_count`, `source_count`,
`confidence ENUM('low','medium','high')`.
PK `(printing_id, condition, day, currency)`.

**Confidence rule:** `high` = ≥ 5 sold observations from ≥ 2 sources in the window; `medium` = ≥ 2
sold observations; `low` = anything else, including anything derived from `listed` prices. The UI
must never show a value without its confidence.

### `price_alerts`
`id`, `user_sub`, `printing_id`, `direction ENUM('above','below')`, `threshold_cents`, `currency`,
`is_active`, `last_fired_at` NULL, `cooldown_hours` DEFAULT 24.

### `fx_rates`
`day DATE`, `base CHAR(3)`, `quote CHAR(3)`, `rate DECIMAL(18,8)`. PK `(day, base, quote)`.
Valuation converts through the day's rate so a EUR user sees stable numbers from USD sales.

---

## Marketplace (phase 3 — deliberately payment-agnostic)

Shaped now so that adding a payment service provider later is an *addition*, never a migration.

### `listings`
`id`, `seller_sub`, `printing_id` NULL, `sealed_product_id` NULL, `condition`, `quantity`,
`unit_price_cents`, `currency`, `description`, `photo_file_ids JSON` (storage-api ids),
`status ENUM('draft','active','reserved','sold','withdrawn','removed')`, `created_at`, `updated_at`.

### `orders`
`id`, `buyer_sub`, `seller_sub`, `status`, `subtotal_cents`, `shipping_cents`, `total_cents`,
`currency`, `created_at`.

Status machine, with the payment states present but unused until the commercial model is chosen:

```
draft → placed → accepted → shipped → delivered → completed
              ↘ declined      ↘ cancelled      ↘ disputed
   (payment_pending / paid / refunded reserved for a PSP integration)
```

### `order_items`
`order_id`, `listing_id`, `quantity`, `unit_price_cents`, `currency`. Prices are **copied**, not
referenced — a later listing edit must not rewrite history.

### `order_events`
Append-only: `order_id`, `at`, `actor_sub`, `type`, `payload JSON`. The order's status is a
projection of this log, so a dispute can always be reconstructed.

### `conversations` / `messages`
`conversation_id`, `listing_id` NULL, participants, then `message_id`, `sender_sub`, `body`,
`sent_at`, `read_at`.

### `seller_ratings`
`id`, `order_id` UNIQUE, `rater_sub`, `rated_sub`, `score TINYINT` 1–5, `comment`, `created_at`.
One rating per order, and only from a completed order — reputation that cannot be manufactured.

---

## Operations

### `app_logs` — our own logging table
Deliberately mirrors the platform's `application_logs` shape so entries are recognisable to anyone
who knows the auth repo, plus a `user_sub` and a `request_id` for joining against our domain.

| Column | Type |
|---|---|
| `id` | `BIGINT` PK AUTO |
| `at` | `DATETIME(6)` |
| `level` | `ENUM('debug','info','warning','error','critical')` |
| `category` | `VARCHAR(48)` — `catalog`, `inventory`, `pricing`, `market`, `security`, `http` |
| `component` / `operation` | `VARCHAR(64)` |
| `message` | `VARCHAR(1024)` |
| `user_sub` | `CHAR(36)` NULL |
| `request_id` | `CHAR(36)` NULL |
| `status_code` | `INT` NULL |
| `duration_ms` | `INT` NULL |
| `context` | `JSON` NULL — secrets and `Authorization` redacted **before** persistence |
| `trace` | `TEXT` NULL |
| `forwarded_to_platform` | `BOOL` DEFAULT 0 |

INDEX `(at)`, `(level, at)`, `(category, at)`, `(user_sub, at)`.
Retention sweep: `debug`/`info` 30 days, `warning`+ 365 days.

### `notification_outbox`
`id`, `user_sub`, `channel`, `template_key`, `context JSON`, `state ENUM('pending','sent','failed')`,
`attempts`, `last_error`, `created_at`, `sent_at`. So a notification-api outage delays mail rather
than losing it.

---

## Index strategy

The three queries that decide whether this app feels fast:

1. **Collection list, filtered** — `inventory_items` by `user_sub` joined to `printings`/`cards`.
   Covered by `(user_sub, printing_id)`; filters on set/element/rarity resolve through the catalog
   side, which is small and cacheable in full.
2. **Set completion** — count of distinct `printings` a user owns within a set, over `sets.card_count`.
   Materialised per user per set in a `set_completion` summary table, invalidated on inventory write.
3. **Price history for a printing** — `price_daily` by PK prefix `(printing_id, condition)`. Never
   touches `price_observations`.

Everything else can be a plain index until measurement says otherwise.
