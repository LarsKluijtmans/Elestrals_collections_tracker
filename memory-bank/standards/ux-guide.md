---
created: 2026-08-09T12:00:00Z
updated: 2026-08-09T12:00:00Z
---

# UX Guide & Brand System

The Construction Agent loads this as optional context for any frontend work. It is the single source
of truth for how the product looks.

---

## 1. Brand position

**Elestral Vault** — a collector's ledger for a mythic card game.

The tension the design has to resolve: the subject matter is *fantasy* (elemental creatures, foils,
arcane runes) but the job is *finance and inventory* (10,000-row tables, price charts, cost basis).
Lean fantasy and it becomes unusable. Lean spreadsheet and it feels like nothing to do with
Elestrals.

**The resolution: a dark, quiet, high-contrast instrument — and the cards supply all the colour.**
Chrome is near-monochrome so that card art, element chips and foil treatments are the only saturated
things on screen. The product looks like a jeweller's tray, not a fairground.

Three words: **precise · dark · elemental.**

---

## 2. Two token layers (architectural, not cosmetic)

The platform resolves branding per company/project and hands us semantic CSS variables. But element
colours are **data encodings** — they must mean the same thing for every tenant, forever. So:

| Layer | Source | Examples | Tenant-variable? |
|---|---|---|---|
| **Chrome tokens** | branding-api `/resolve` → `themeFromBranding()` | primary, surfaces, focus ring, link | **Yes** |
| **Domain tokens** | hard-coded constants in `theme/domain.ts` | 8 element hues, rarity materials, price up/down | **No — never** |

If a tenant sets their primary to green, buttons go green. Wind stays wind.

---

## 3. Colour

### Neutrals — dark (default)

| Token | Value | Use |
|---|---|---|
| `--bg-0` | `#0A0D16` | page ground |
| `--bg-1` | `#111623` | cards, panels |
| `--bg-2` | `#191F31` | raised, hover |
| `--bg-3` | `#222A40` | popovers, active row |
| `--border-subtle` | `#262E44` | dividers, card outline |
| `--border-strong` | `#38425E` | inputs, focus-adjacent |
| `--fg-1` | `#EAEEF9` | primary text |
| `--fg-2` | `#A3AFC9` | secondary text |
| `--fg-3` | `#6C7896` | muted, placeholders |

### Neutrals — light

| Token | Value |
|---|---|
| `--bg-0` | `#F7F8FC` |
| `--bg-1` | `#FFFFFF` |
| `--bg-2` | `#F1F3F9` |
| `--bg-3` | `#E7EAF3` |
| `--border-subtle` | `#E2E6F0` |
| `--border-strong` | `#C7CEDF` |
| `--fg-1` | `#131826` |
| `--fg-2` | `#4A5570` |
| `--fg-3` | `#737E99` |

### Brand accent (chrome layer — tenant-overridable)

| Token | Dark | Light |
|---|---|---|
| `--brand` | `#7B5CFF` | `#6544E8` |
| `--brand-hover` | `#9179FF` | `#5738D4` |
| `--brand-pressed` | `#6647E6` | `#4A2FBA` |
| `--brand-ring` | `rgba(123,92,255,.45)` | `rgba(101,68,232,.35)` |

### Elements (domain layer — fixed)

The eight core Elestrals elements. Values are tuned for the dark theme; the light column is darkened
for AA on white.

| Element | Dark | Light |
|---|---|---|
| Fire | `#FF6A5A` | `#C7392B` |
| Solar | `#FFA033` | `#B36405` |
| Thunder | `#FFD84D` | `#8A6B00` |
| Wind | `#4FDD9B` | `#0E7A50` |
| Frost | `#5FDDEC` | `#0A7286` |
| Water | `#5AA0FF` | `#1257C4` |
| Lunar | `#B69BFF` | `#6A46CF` |
| Earth | `#D2A06B` | `#8A5A22` |

> **The chip rule.** Element colour is *never* a solid fill. An element chip is the hue at 14% alpha
> as background, the hue at full strength as text and 1px border. Solid saturated fills are reserved
> for the brand accent, so a chip can never be mistaken for a button. This is also what keeps Lunar
> (`#B69BFF`) from colliding with the brand violet — different treatment, not different hue.
>
> Chips always carry the element **name**, not just the colour. Colour is redundant encoding.

### Semantic

| Token | Dark | Light | Use |
|---|---|---|---|
| `--success` | `#35C77F` | `#0E7A50` | saved, in stock |
| `--warning` | `#F0B429` | `#8A6100` | stale price, low confidence |
| `--danger` | `#F0524B` | `#C0342E` | destructive, failed run |
| `--info` | `#5AA0FF` | `#1257C4` | neutral notices |

### Price movement

`--price-up: #35C77F`, `--price-down: #F0524B`, `--price-flat: var(--fg-3)`.

**Always paired with a glyph** — `▲ +12.4%` / `▼ −3.1%` / `– 0.0%`. Roughly 1 in 12 men has a
red-green deficiency and this product is fundamentally about red and green numbers; colour alone is
not acceptable here.

---

## 4. Four independent encodings that must never collide

This is the rule that keeps a dense card row legible:

| Attribute | Encoded as | Never encoded as |
|---|---|---|
| **Element** | hue (8 chips, tinted) | shape, position |
| **Rarity** | *material* — flat / ring / gradient / iridescent border | hue |
| **Condition** | neutral grey badge with a letter grade (`NM`, `LP`, `MP`, `HP`, `DMG`) | colour |
| **Price movement** | green/red **+ arrow glyph** | hue alone |

### Rarity materials

| Rarity | Treatment |
|---|---|
| Common | flat `--fg-3` text, no border |
| Uncommon | flat `--fg-2` text, 1px `--border-strong` ring |
| Rare | silver — `linear-gradient(135deg,#C9D2E4,#8A97B4)` 1px border |
| Holo Rare | silver border + a slow 4s diagonal sheen sweep |
| Full Art / Alt Art | 1.5px gradient border in the card's element hue |
| Prismatic / Secret | 1.5px `conic-gradient` iridescent border |
| Promo | dashed 1px `--border-strong` |

All sheen and shimmer animation is suppressed under `prefers-reduced-motion: reduce`.

---

## 5. Typography

| Role | Family | Fallback stack |
|---|---|---|
| Display (h1–h3, hero numbers) | **Sora** 600 | `ui-sans-serif, system-ui, "Segoe UI", sans-serif` |
| Body / UI | **Inter** 400/500/600 | same |
| Code / logs | **JetBrains Mono** 400 | `ui-monospace, "Cascadia Code", monospace` |

**Every number is tabular.** `font-variant-numeric: tabular-nums` is set globally on `body` and must
not be unset — prices in a column have to align or the table is unreadable.

Scale — 1.25 major third from a 16px base:

| Step | px | Use |
|---|---|---|
| `xs` | 12 | chips, table meta, captions |
| `sm` | 14 | table body, secondary |
| `base` | 16 | body |
| `lg` | 20 | card titles, section heads |
| `xl` | 25 | page titles |
| `2xl` | 31 | dashboard hero stat |
| `3xl` | 39 | landing headline |
| `4xl` | 49 | landing hero |

Line height 1.5 for body, 1.2 for display. Max measure 68ch for prose.

---

## 6. Space, radius, elevation, motion

- **Spacing** — 4px base: `4 · 8 · 12 · 16 · 24 · 32 · 48 · 64`. Nothing off-scale.
- **Radius** — `6` chips/inputs, `10` cards/panels, `16` modals/sheets, `999` pills.
- **Elevation on dark is a surface step, not a shadow.** `--bg-1` → `--bg-2` → `--bg-3` plus a 1px
  `--border-subtle`. Shadows are a faint accent only: `0 1px 2px rgba(0,0,0,.4)` resting,
  `0 8px 24px rgba(0,0,0,.5)` for overlays. Big soft shadows read as mud on a `#0A0D16` ground.
- **Motion** — 120ms `ease-out` hover/press, 200ms panels and sheets, 4s foil sheen loop. No motion
  above 300ms on anything in the interaction path.

---

## 7. Layout

- **App shell**: fixed 240px left rail (collapses to 64px icon rail < 1280px, becomes a bottom tab
  bar < 900px), 56px top bar with global search, notification bell and account menu.
- **Content max width** 1440px, gutters 24px desktop / 16px mobile.
- **Grid** 12 columns desktop, 8 tablet, 4 mobile.
- **Breakpoints** `sm 600 · md 900 · lg 1280 · xl 1680`.

### Density modes

The collection table ships with a user-toggled density, because the two personas want opposite
things:

| Mode | Row height | For |
|---|---|---|
| Comfortable | 56px | browsing, thumbnails visible |
| Compact | 36px | the investor scanning 500 rows |

---

## 8. Core components

| Component | Spec |
|---|---|
| **CardTile** | 3:4 art, element chip top-left, rarity material as the tile border, quantity badge bottom-right, price + delta on hover. Skeleton has the same aspect ratio so the grid never reflows. |
| **CardRow** | thumbnail 32px · name · set code · element chip · rarity chip · condition badge · qty stepper · unit value · line value · row menu. |
| **QtyStepper** | `−` / value / `+`, optimistic, debounced 400ms, reverts with an inline toast on failure. The single most-used control in the app — it gets a 44px hit target. |
| **CompletionRing** | SVG ring, `owned/total` centred, ring stroke in the set's dominant element hue, grey track. |
| **PriceSparkline** | 30-day line, no axes, last point dotted, tinted area fill. Colour follows the period's direction. |
| **ConfidencePill** | `high` filled `--success` / `medium` outlined `--warning` / `low` outlined `--fg-3` with a tooltip explaining the observation count. **No monetary figure renders without one.** |
| **EmptyState** | line illustration, one sentence, one primary action. Every list has one written before the list is built. |
| **StatTile** | label `xs` `--fg-2`, value `2xl` display, delta line with glyph. Used across dashboard and portfolio. |

---

## 9. Accessibility (binding, not aspirational)

- WCAG **2.2 AA**: 4.5:1 body text, 3:1 large text and UI boundaries. The palettes above are chosen
  to satisfy this in both themes.
- Never colour alone — element chips carry names, price deltas carry arrows, rarity carries a label.
- Visible focus on every interactive element: 2px `--brand-ring` offset 2px. Never `outline: none`.
- Full keyboard path through add-card, the collection table and checkout. The add flow is
  keyboard-only end to end because that is how anyone entering 200 cards will actually use it.
- All imagery has alt text; card images use `"{name} — {set} {rarity}"`.
- `prefers-reduced-motion` disables shimmer, sheen and chart entry animation.
- Live regions announce optimistic saves and their failures.

---

## 10. Voice

Plain, exact, never breathless. `"No cards yet"` not `"Your vault awaits!"`. Numbers always carry
their unit and currency. Uncertainty is stated, never hidden: `"Estimated €412 · low confidence ·
based on 3 sales in 30 days"` beats a confident wrong number every time.

---

## 11. Page inventory

Auth: **P** = public, **A** = authenticated, **R** = RBAC-gated (operator).

### Phase 1 — collection tracker

| # | Route | Auth | Purpose | Key elements |
|---|---|---|---|---|
| 1 | `/` | P | Landing | Hero, three value props, sample dashboard screenshot, sign-in CTA |
| 2 | `/login` | P | Sign-in gate | Embedded `<LoginForm>`, branded, EN/NL switch |
| 3 | `/dashboard` | A | Home after sign-in | 4 StatTiles (items, distinct printings, sets started, est. value), completion rings for 3 nearest sets, recent activity, "add cards" CTA |
| 4 | `/collection` | A | The main table | Virtualized CardRow list, filter rail (set, element, rarity, condition, finish, language, graded, for-trade), density toggle, saved views, bulk select → bulk edit/delete/export |
| 5 | `/collection/add` | A | Fast entry | Search-as-you-type, keyboard-only, printing/condition pickers remembered between adds, running session tally, undo |
| 6 | `/collection/add/set/:setCode` | A | Grid entry | Whole-set grid, click a card to +1, shift-click to −1. The fastest way to enter a bulk lot |
| 7 | `/sets` | P | Set gallery | Set cards with CompletionRing (rings only when signed in) |
| 8 | `/sets/:setCode` | P | Set checklist | Full printing grid, owned/missing/all toggle, completion %, "export missing" |
| 9 | `/cards/:cardId` | P | Card detail | Art, stats, rules text, all printings table, my copies, price tab (p2), listings tab (p3) |
| 10 | `/sealed` | A | Sealed inventory | Packs, boxes, decks; sealed vs opened |
| 11 | `/wishlist` | A | Wanted | Printing, desired qty, max price, priority; "alert me" (p2) |
| 12 | `/import-export` | A | CSV | Upload → column mapper → dry-run diff → commit; export current filter |
| 13 | `/settings/profile` | A | Profile | Enriched from auth-api; handle, visibility, currency, condition scale; avatar via storage-api |
| 14 | `/settings/notifications` | A | Channels | Email / in-app / push per event type |
| 15 | `/u/:handle` | P | Public collection | Only if visibility is `public`/`link`; read-only, no cost basis ever |
| 16 | `/admin/catalog` | R | Operator | Import runs, catalog health, staleness, rejected rows |

### Phase 2 — price intelligence

| # | Route | Auth | Purpose |
|---|---|---|---|
| 17 | `/prices` | P | Market overview: top movers, set indices, most-traded |
| 18 | `/cards/:cardId` → price tab | P | History chart, per-condition/finish breakdown, source list, confidence, recent sales table with links |
| 19 | `/portfolio` | A | Value over time, cost basis vs market, unrealized P/L, breakdown by set/element/rarity, best and worst performers |
| 20 | `/portfolio/slice` | A | Value *any* filtered slice — the "what is my Fire collection worth" answer |
| 21 | `/alerts` | A | Price alerts, threshold, direction, cooldown, fire history |
| 22 | `/admin/scrapers` | R | Per-source health, last run, accept/reject rates, ToS review state, kill switch |

### Phase 3 — marketplace

| # | Route | Auth | Purpose |
|---|---|---|---|
| 23 | `/market` | P | Browse listings; filters mirror `/collection`; price-vs-market column |
| 24 | `/market/:listingId` | P | Listing detail, seller card, price-vs-market verdict, photos |
| 25 | `/sell/new` | A | Create listing, prefilled from inventory, suggested price from `price_daily` |
| 26 | `/sell` | A | My listings, views, offers |
| 27 | `/orders` | A | Buying / selling tabs, status timeline from `order_events` |
| 28 | `/messages` | A | Conversations, per-listing threads |
| 29 | `/u/:handle` (extended) | P | Seller reputation, rating history, active listings |
| 30 | `/admin/trust` | R | Reports queue, listing takedowns, user suspension |

**28 user-facing routes + 3 operator routes**, with 15 of them in phase 1.

---

## 12. The two interactions worth over-investing in

Everything else can be conventional. These two decide whether the product is used twice:

1. **Adding a card (`/collection/add`).** A collector with a 400-card box will abandon anything
   slower than a few seconds per card. Target: type 3 characters → arrow to the printing → `Enter`
   → it is saved and the field is cleared and focused, under 5 seconds, hands never leaving the
   keyboard. Condition and finish persist from the previous add because a box is usually uniform.

2. **Reading a value (`/portfolio`).** The number must be trustworthy or the whole of phase 2 is
   decoration. Always show what it is built from — how many sales, over what window, from how many
   sources — and never round away the uncertainty. A visible `low confidence` pill is worth more
   than a precise-looking lie.
