---
intent: 001-collection-tracker
phase: inception
status: complete
created: 2026-08-09T12:00:00Z
updated: 2026-08-09T12:00:00Z
---

# Inception Log: 001-collection-tracker

## Session 1 — 2026-08-09

### Checkpoint 1 — Clarifying questions ✅

Four questions were put before any artifact was written, because each one changed the shape of the
work materially.

| # | Question | Answer |
|---|---|---|
| 1 | What should the app be built on? | **Fork `../app-starter`** — React + Vite + MUI + FastAPI. SPA trade-off (no SEO on public pages) accepted |
| 2 | Where should the data live? | **Own `elestrals` database on the platform's MySQL**, own Alembic tree, own `app_logs` |
| 3 | How is the card catalog seeded? | **Scrape and import, we own it** — a re-runnable importer per set |
| 4 | Phase-3 marketplace commercial model? | **Decide in phase 3** — phases 1 and 2 in full detail, phase 3 costed both ways and kept payment-agnostic |

### Research performed

- Read the platform's `docs/ARCHITECTURE.md` and `docs/INTEGRATION.md` to establish which services
  this app consumes and how.
- Read `../app-starter` to confirm it wires login, branding, i18n and platform logging — and that it
  has **no persistence layer**, which is the gap this project fills.
- Confirmed the Elestrals domain vocabulary from public sources: three card types (Elestrals,
  Spirits, Runes), five rune types (Invoke, Counter, Artifact, Stadium, Divine), and **eight**
  elements (Earth, Fire, Water, Thunder, Wind, Frost, Solar, Lunar). The eight elements drive the
  element palette in `standards/ux-guide.md`.

### Checkpoint 2 — Requirements review ⏳ awaiting user

18 functional requirements, NFRs across performance, scalability, security, reliability and
compliance. 5 open questions, 2 of which are resolved.

### Artifacts generated (auto-continue: context → units → stories → bolt-plan → review)

| Artifact | Path |
|---|---|
| Project brief | `memory-bank/project/project-brief.md` |
| Tech stack | `memory-bank/standards/tech-stack.md` |
| System architecture | `memory-bank/standards/system-architecture.md` |
| Data model | `memory-bank/standards/data-model.md` |
| UX guide + brand system | `memory-bank/standards/ux-guide.md` |
| Requirements | `intents/001-collection-tracker/requirements.md` |
| System context | `intents/001-collection-tracker/system-context.md` |
| Units | `intents/001-collection-tracker/units.md` (7 units) |
| Unit briefs | `intents/001-collection-tracker/units/*/unit-brief.md` (7) |
| Stories | `intents/001-collection-tracker/units/*/stories/` (36) |
| Bolt plan | `intents/001-collection-tracker/bolt-plan.md` (9 bolts) |
| Bolt instances | `memory-bank/bolts/*/bolt.md` (9) |
| Story index | `memory-bank/story-index.md` |

## Decisions taken during inception

| Decision | Rationale |
|---|---|
| **`printings` is the SKU** — set → card → printing, with condition on the holding | A collector owns a specific physical object, and prices attach to that object, not to a card name. Every later feature is a query over `printings`; getting the grain wrong is the most expensive available mistake |
| **Two token layers**: chrome from branding-api, domain colours hard-coded | Element colours are data encodings. They must mean the same thing for every tenant, forever |
| **Four independent visual encodings**: element = hue, rarity = material, condition = neutral letter badge, price move = colour **plus** glyph | Prevents a dense card row from becoming unreadable, and keeps the product usable with a red-green colour deficiency |
| **Catalog unit before inventory unit** | Inventory is more central; the catalog is where the intent can *fail*. De-risk what can kill the project, not what is biggest |
| **Entry bolt before browse bolt** | Browsing an empty collection proves nothing. Entry first makes the 5s / 10min targets measurable rather than estimated |
| **Merge-on-duplicate via upsert, never read-then-write** | The fast-add flow fires concurrent requests by design. Read-then-write passes every sequential test and loses rows in production |
| **Own `app_logs` *and* forward to logs-api**, routed inside one `log_event()` helper | The user asked for both. One call site means the rule can change once |
| **`collection_snapshots` written in phase 1, read in phase 2** | Portfolio history otherwise starts empty on the day phase 2 ships. Cheap insurance taken a year early |
| **Public collection view is a whitelist model, not a filtered one** | Filtering is a rule someone forgets to apply to the next field. A separate model that never had cost basis cannot leak it |
| **One file per story** — `{SSS}-{title-slug}.md`, 36 of them | Initially consolidated into a `stories.md` per unit to avoid ceremony. **Reversed**: `artifact-validator.cjs` reported 38 errors, because every bolt's `stories:` array is a cross-reference resolved against those filenames. Consolidation broke the toolchain's own integrity checks and would have starved the Construction Agent of the per-story files it loads. The five highest-risk stories keep deeper edge-case tables; the rest are complete but tighter |
| **Unit and intent statuses use the tooling's vocabulary** (`stories-defined`, `units-defined`) | `status-integrity.cjs --fix` owns these transitions and derives them from bolt completion. Hand-authored values drifted immediately; letting the script own them keeps the state machine honest |

## Risks recorded

| Risk | Where handled |
|---|---|
| Trademark / affiliation with the publisher | `project-brief.md` risks; unofficial notice required on every page |
| Card image rights | Store URLs not bytes; one config switch to storage-api once permission exists |
| Public card data may be unusable | Bolt 002 opens with a one-day spike; CSV seed is the fallback |
| Price-source terms of service | Intent 002: `tos_review_note` gates enablement at the database level |
| JWT `sub` stability | Bolt 001 verifies before anything is keyed on it |

## Checkpoint 3 — Artifacts review ⏳ awaiting user

## Checkpoint 4 — Ready for construction ⏳ pending checkpoints 2 and 3

**Next**: on approval, hand to the Construction Agent starting at bolt `001-platform-foundation`.
