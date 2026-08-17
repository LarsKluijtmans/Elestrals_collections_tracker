---
intent: 002-price-intelligence
phase: inception
status: complete
created: 2026-08-09T12:00:00Z
updated: 2026-08-15T15:20:00Z
---

# Inception Log: 002-price-intelligence

## Session 1 — 2026-08-09

Requirements, system context and unit decomposition drafted alongside intent 001, against an
assumption that has since been tested and found false: that at least two sources would permit access
to sold-price data on acceptable terms.

Artifacts: `requirements.md` (12 FRs), `system-context.md`, `units.md` (6 units, 24 stories,
enumerated but not elaborated).

Left open: *"Which sources have an official API for sold data, and on what terms?"* — owner Lars, due
before unit 002.

---

## Session 2 — 2026-08-12 — the source spike

That open question was taken as a spike before any bolt was planned, because it decided whether the
intent was buildable at all.

**Finding**: every direct route is closed. TCGplayer's API has not accepted new applicants since late
2024; eBay's Marketplace Insights is a Limited Release that is "restricted and not open to new
users"; eBay Browse is open but returns active listings only; scraping either is prohibited by their
terms. One obtainable source carries Elestrals — a licensed aggregator at $49.99/mo, refreshing every
3 days, supplying aggregate market prices rather than a transaction feed.

Recorded as **ADR-003**, status `proposed` rather than accepted, because it cost money and that was
not the agent's decision. The ADR also flagged that FR-2, FR-3 and FR-4 would all need weakening
before construction if it were accepted, since an aggregate feed cannot supply sale counts, sale
windows or comparables.

---

## Session 3 — 2026-08-15 — the decision, and a re-cut

### The decision ADR-003 was waiting for

Put to the human, and answered: **do not pay, scrape it all.** With two further changes: run the
harvester as a **second backend**, and put the raw harvested data behind an **admin** claim.

Recorded as **ADR-004**, status `accepted`, risk owner Lars Kluijtmans. ADR-003 marked `superseded`
— its research stands and is why ADR-004 exists; its conclusion does not.

### Checkpoint 1 — Clarifying questions ✅

Five questions were put before any artifact was rewritten. Four changed the shape of the work; the
fifth decided how much of the intent survived at all.

| # | Question | Answer |
|---|---|---|
| 1 | How does the second backend relate to the existing database? | **Own schema `elestrals_harvest`, same MySQL instance**, isolated by grants |
| 2 | Where does the `admin` claim come from? | **A new `elestrals:admin` scope** on the platform token, extending the phase-1 operator pattern |
| 3 | How aggressive should the scrapers be? | **Assertive** — robots.txt not obeyed, rates set for throughput, user agent still honest |
| 4 | What can admins do with the data? | **Operate and analyse** — run both scans, inspect every listing, judge coverage and match quality |
| 5 | Does admin-only kill the user-facing price features? | **No** — raw harvest is admin-only; `price_daily` rollups still feed the collector surfaces |

Answer 5 was asked separately, after the first four, because getting it wrong would have invalidated
the entire unit and bolt plan: "admin-only" could have meant four of six units dropping out.

### The consequence nobody expected

Scraping **restores FR-4** rather than weakening it. ADR-003 was going to force FR-2, FR-3 and FR-4
to be amended because the licensed feed supplies aggregate market prices with no sale count, window
or comparables. Scraped completed-listings pages carry the actual sale price and the actual sale
date. The decision taken on cost grounds turns out to deliver the *stronger* product on the one
requirement the whole valuation rests on — and that is now the technical argument in ADR-004,
recorded next to the risk rather than instead of it.

### Checkpoint 2 — Requirements review ✅ approved

18 functional requirements, up from 12. Changed: FR-1 (legal veto → recorded risk acceptance), FR-2
(one daily job → two scan modes), FR-5 (adds the publication constraint), FR-12 (folded into the
admin console). Restored intact: FR-4. New: FR-13 (second backend), FR-14 (admin authorisation),
FR-15 (data explorer), FR-16 (analysis), FR-17 (run control), FR-18 (survive being blocked).

Business goal "Legality" replaced by "**Risk is recorded**" — the terms review stays mandatory
before enablement, because you cannot accept a risk you have not read, but it no longer has a veto.
NFR §Conduct rewritten to state plainly that robots.txt is not obeyed; recorded rather than left
implicit, because a convention broken silently reads as one nobody knew about.

### Artifacts regenerated

| Artifact | Change |
|---|---|
| `requirements.md` | 12 → 18 FRs; NFRs restructured; goals amended |
| `system-context.md` | Two backends, two schemas, grant-enforced boundary, admin actor, `price_daily` as the sole contract |
| `units.md` | 6 units / 24 stories → **7 units / 34 stories** |
| `units/*/unit-brief.md` | 7 briefs written |
| `units/*/stories/*.md` | 34 stories elaborated |
| `bolt-plan.md` | **New** — 8 bolts, numbered 010–017 |
| `adr-004-scrape-over-licence.md` | **New** — accepted, with risk owner and review triggers |
| `adr-003-price-source.md` | Marked superseded |
| `decision-index.md` | ADR-004 added; ADR-003's "read when" narrowed to the map it still provides |
| `story-index.md` | 36 → 70 stories |

### Unit re-cut

`pipeline-infrastructure` became **`harvest-service`**, because the pipeline is now a service and
its schema, grants, container and release path are its first deliverables rather than incidental to
them. `source-connectors` became **`scrapers`** and gained block detection. `alerts-and-ops` was
**split**: the ops console grew from one story into the primary surface of the intent and became
`admin-console`, leaving `alerts` as its own small unit rather than sharing one for no reason beyond
both being leftovers.

### The ordering decision

**Bolt 013 (admin console) is scheduled before bolt 014 (rollups and valuation)**, against the
obvious order. Under ADR-004 every number comes from scraped pages of uneven quality, and the console
is the only means of finding out whether the matcher is placing titles correctly. Building valuation
first would mean discovering a systematic matcher error through a user's portfolio figure — the
latest and most expensive place to find it. Bolt 013 is the intent's judgement gate: if the explorer
shows a low accept rate or implausible prices, bolts 14–17 wait.

### Checkpoint 3 — Artifacts review ✅ approved

7 units, 34 stories, 8 bolts. All 18 FRs trace to at least one story; all 34 stories are assigned to
a bolt; no circular unit dependencies. Story ids match filenames and unit names match folders,
verified by hand — `artifact-validator.cjs` could not be run because `fs-extra` is not installed in
this environment, which is a pre-existing gap rather than something this session introduced.

### Checkpoint 4 — Ready for construction ✅

Bolt instances created at `memory-bank/bolts/010-…` through `017-…`, all `planned`.

---

## Summary

- **Functional Requirements**: 18
- **Non-Functional Requirement groups**: 6 (performance, scalability, security & authorisation,
  conduct, reliability, compliance)
- **Units**: 7
- **Stories**: 34 (32 Must, 2 Should)
- **Bolts Planned**: 8 (7 DDD, 1 simple)
- **ADRs**: ADR-004 accepted; ADR-003 superseded

## Ready for Construction

- [x] All requirements documented
- [x] System context defined
- [x] Units decomposed
- [x] Stories created for all units
- [x] Bolts planned
- [x] Human review complete

## Next Steps

→ `/specsmd-construction-agent --unit="001-harvest-service"` — bolt `010-harvest-service-foundation`

### Open questions carried into construction

| Question | Gates | Owner |
|---|---|---|
| Can the platform issue an `elestrals:admin` scope? | bolt 013 | Lars |
| At what point does a block become a stop rather than a backoff? | bolt 011 | Lars |
| Median or trimmed mean as the headline figure? | bolt 014 | Lars |
| Does a licensed agreement become necessary once the marketplace charges a fee? | phase 3 | Lars |

The first two are new, and both come from ADR-004. The scope question is the more serious: without
it, FR-14 falls back to a subject allowlist, which is a development convenience rather than an
authorisation system.
