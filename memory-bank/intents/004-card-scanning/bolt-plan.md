---
intent: 004-card-scanning
phase: inception
status: bolts-planned
created: 2026-08-17T14:40:00Z
updated: 2026-08-17T14:40:00Z
---

# Card Scanning — Bolt Plan

**7 bolts, 38 stories, 7 units.** Five DDD bolts and two simple bolts. Numbering continues the global
sequence from intent 002, which ended at bolt 017.

## Bolt sequence

| # | Bolt | Unit | Stories | Type | Complexity | Uncertainty |
|---|---|---|---|---|---|---|
| 18 | `018-pilot-catalog` | 001 | 4 | simple | 2 | **3** |
| 19 | `019-scan-service-foundation` | 002 | 6 | DDD | 3 | 2 |
| 20 | `020-identification-ladder` | 003 | 6 | DDD | 3 | **3** |
| 21 | `021-evaluation-harness` | 004 | 4 | DDD | 2 | 2 |
| 22 | `022-curation-console` | 005 | 6 | DDD | 3 | 1 |
| 23 | `023-mobile-app-shell` | 006 | 6 | simple | 2 | 2 |
| 24 | `024-scan-experience` | 007 | 6 | DDD | 3 | 1 |

## Dependency graph

```text
018-pilot-catalog                          ← THE GO/NO-GO
   └─> 019-scan-service-foundation
          └─> 020-identification-ladder
                 └─> 021-evaluation-harness ← THE HONESTY GATE
                        ├─> 022-curation-console
                        └─> 024-scan-experience
                                 ▲
023-mobile-app-shell ────────────┘
   (parallelisable from the start — depends only on intent 001)
```

Bolts 18 to 21 are strictly sequential and there is no useful way to parallelise them: nothing to
identify without a catalog, nowhere to run without a service, nothing to measure without an engine,
and nothing honest to display without a measurement.

**Bolt 23 is the exception, and it should be exploited.** The mobile app shell depends on nothing in
this intent — only on intent 001's platform foundation. It can start on day one, in parallel with
18–21, by anyone not working on the recogniser. Its one external dependency (the `login-api` client
registration) is already resolved and can be requested immediately rather than discovered on the day
the app needs it.

## Risk-driven ordering

The sequence is not the dependency graph's only valid topological sort. Three choices were made
deliberately.

**Bolt 18 is the go/no-go, and it opens with a spike.** It carries an uncertainty-3 rating for the
same reason bolt 002 did in intent 001 and bolt 011 did in intent 002: it is where this intent can
fail. The bolt should open with a **thin slice** — compile ~20 cards, photograph them, run on-device
OCR, measure — before completing the remaining 106. Twenty cards is enough to detect a catastrophic
result, and a catastrophic result here means the ladder architecture is wrong and six bolts need
re-cutting. Discovering that in week one costs a week; discovering it in bolt 24 costs the intent.

**Bolt 21 comes before both surfaces**, against the obvious order of "build the product, then measure
it". FR-5 puts a percentage next to a card name, and FR-15 is the only thing that makes that
percentage true. Building bolt 24 first would mean shipping a raw model score dressed as an accuracy
claim, and then trying to retrofit honesty onto a number users had already been shown. This is the
same reasoning that put intent 002's admin console before its valuation, and it was right there.

**Bolt 22 comes before bolt 24**, though it does not strictly block it. Two reasons: the scan flow's
candidate lists are markedly more usable with card images in them, and — more importantly — bolt 22 is
where you find out whether the captures are any good. If curation shows the corpus filling with
unusable photographs, that is a fact worth having before the flow that generates them ships to
everyone.

## Milestones

| After bolt | The product can… | Worth showing to |
|---|---|---|
| **018** | **tell you whether a phone can read an Elestrals card at all** | **yourself — this is the go/no-go on the whole intent** |
| 019 | store a capture, hold a fingerprint, and fail without touching the collection tracker | nobody — but every later bolt starts from an isolated service |
| 020 | identify a card from a photograph, end to end | yourself, through a test harness |
| **021** | **say how often it is right, and prove it** | **yourself, seriously — this is where you decide whether the numbers can be shown to anyone** |
| 022 | turn a pile of captures into a curated corpus, and give the catalog its first images | yourself |
| 023 | put a signed-in app on a phone that shows your collection | first external testers |
| **024** | **scan a card and record that you own it, on both surfaces** | **everyone — this is the intent** |

**Bolt 021 is the decision point of this intent.** If the harness shows top-1 well below 90%, or
calibration wildly off, bolts 22 and 24 should not ship a percentage. The product can still ship with
qualitative confidence bands — that is story 015's designed fallback — but that is a decision to take
knowingly at bolt 21, not a discovery at bolt 24.

**Bolt 024 is the minimum shippable increment for users.** Nothing before it is visible to a collector,
except the card images that appear during bolt 22.

## Bolt types

Five DDD bolts, because each introduces or changes domain rules — the service boundary and its grants,
the ladder and its thresholds, the dataset and split invariants, the curation state machine, and the
scan-to-inventory flow with its concurrency contract.

Two simple bolts:
- **018-pilot-catalog** is data compilation plus a measurement. It introduces no domain rule and
  changes no code — the importer is explicitly out of scope for modification.
- **023-mobile-app-shell** is client construction against existing endpoints and an existing auth
  flow. Its complexity is toolchain, not domain.

## What this plan assumes

| Assumption | If wrong |
|---|---|
| On-device OCR can read an Elestrals card's name and collector number | The ladder's cheap path collapses, latency triples, offline scanning dies, and FR-3 cannot be kept. **Tested in bolt 018's opening spike** |
| A cropped photograph is enough for reliable image matching | Pass 2's target is unreachable and the ladder is OCR-only in practice. Known at bolt 021, measured rather than assumed |
| A linear scan over 50k fingerprints fits the 1.2s budget | A vector index is needed. ADR-002's precedent applies: measure first, and let the measurement justify the index |
| `/collection` exists by the time bolt 023 needs it | **It does not today.** Intent 001's bolt 006 is unbuilt, so stories 029–031 are blocked on it. This is the plan's most concrete external risk |
| Users will confirm a printing rather than abandoning at the extra tap | The flywheel gets no finish labels and the V2 intent has nothing to train on. Measured at bolt 024 |
| Enough captures arrive to grow the corpus | Coverage stays at whatever was photographed in bolt 018 — which still works, just narrowly |

## Open questions that gate bolts

| Question | Gates | Owner | Status |
|---|---|---|---|
| Which set is the pilot — FE01, or one owned more completely? | bolt 018 | Lars | **Pending** — a set you can photograph end to end is worth more than the first set numerically |
| Has intent 001's bolt 006 shipped `/collection`? | bolt 023, stories 029–031 | Lars | **Pending** — currently `planned` in the story index |
| Does an Apple signing identity become available? | iOS only | Lars | **Pending** — gates nothing in this intent by design |
| Is a linear fingerprint scan fast enough, or is an index needed? | bolt 020 | Lars | **Pending** — decide on measurement, record as an ADR either way |

## ADRs required before or during construction

| ADR | Subject | Bolt | Why it cannot be implicit |
|---|---|---|---|
| ADR-006 | Seeded reference images — accepted risk, bounded and shrinking | 019 (story 010) | Knowing exception to the data model's "URLs never bytes" rule and to ADR-001. Needs a named risk owner and review triggers |
| ADR-007 | Public display of user-submitted card photographs after admin approval | 022 (story 022) | The artwork in a user's photograph is still the publisher's. The decision was taken on 2026-08-17 with a condition attached; the condition is what makes it defensible and it belongs on the record |

Numbering continues from ADR-005. Both are created by the Construction Agent during their bolts, per
the ownership rules in `memory-bank.yaml` — inception names them rather than writing them.
