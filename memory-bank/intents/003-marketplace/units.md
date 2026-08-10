---
intent: 003-marketplace
phase: inception
status: outline
updated: 2026-08-09T12:00:00Z
---

# Marketplace - Unit Decomposition (outline)

**Route A: 4 units, ~13 stories. Route B: those 4 plus 3 more, ~21 stories.**

Units 001–004 are identical under both routes. That is the point of deferring the decision — the
first two-thirds of the work is the same either way, so building it does not commit us.

---

### Unit 001: listings

**Stories**: 001-create-listing-from-inventory · 002-listing-lifecycle · 003-listing-photos ·
004-inventory-reservation

Create, edit, withdraw. Prefilled from a holding, with a suggested price from `price_daily` and its
confidence. Listing reserves against the holding so the same physical copy cannot be sold twice.
Photos are end-user `owned` files in storage-api.

**Depends on**: intent 001 units 003 and 007; intent 002 unit 004. **Complexity**: M

---

### Unit 002: discovery

**Stories**: 005-browse-and-filter · 006-listing-detail · 007-price-vs-market-verdict

Filters mirroring `/collection`, and on every result the verdict that justifies this marketplace
existing at all: *"€24 · 12% below the 30-day median · high confidence"*. Without intent 002 behind
it this is just another classifieds page.

**Depends on**: 001. **Complexity**: M

---

### Unit 003: messaging-and-orders

**Stories**: 008-conversations · 009-place-order · 010-order-status-machine · 011-order-timeline

Per-listing threads, rate-limited and reportable. Orders copy prices rather than referencing them.
Status is a **projection of the append-only `order_events` log**, never a mutable column — so a
disputed order can be reconstructed exactly as it happened.

**Depends on**: 002. **Complexity**: L

---

### Unit 004: reputation-and-safety

**Stories**: 012-seller-ratings · 013-reports-and-takedowns

One rating per completed order, only from a completed order. Reporting with a counterfeit-specific
reason, an operator queue, takedowns and suspension.

**Depends on**: 003. **Complexity**: M

---

## Route B only — the additional cost of taking money

### Unit 005: payments-and-escrow
**Stories**: 014-psp-integration · 015-checkout · 016-hold-and-release · 017-refunds
**Complexity**: XL

### Unit 006: seller-onboarding-and-payouts
**Stories**: 018-kyc-onboarding · 019-payout-scheduling
**Complexity**: L — KYC/AML is mostly not code; it is process, vendor and obligation

### Unit 007: disputes-and-compliance
**Stories**: 020-dispute-resolution · 021-tax-and-regulatory-reporting
**Complexity**: L — and unlike everything else here, it never finishes: it becomes ongoing
operational load

---

## Dependency graph

```text
[001 listings] ─> [002 discovery] ─> [003 messaging-and-orders] ─> [004 reputation-and-safety]
                                              │
                                              └─(route B)─> [005 payments] ─> [006 payouts] ─> [007 disputes]
```

## Costing the decision

| | Route A | Route B |
|---|---|---|
| Units | 4 | 7 |
| Stories | ~13 | ~21 |
| Largest unit | messaging-and-orders (L) | payments-and-escrow (XL) |
| Comparable to | intent 001 | intents 001 + 002 together |
| Ongoing load after launch | moderation | moderation + disputes + chargebacks + payouts + tax filing, permanently |
| Reversible | yes | **no** — regulatory obligations do not switch off |

The asymmetry is the argument: route A can become route B later, and the listing and reputation
history it produces is exactly what makes route B safe to launch. Route B cannot become route A.

## Recommendation for the phase-3 decision

Build units 001–004. Run them. If listing volume and completed off-platform trades justify the cost
of units 005–007 — and the regulatory questions in `requirements.md` have real answers — add them
then, on top of a marketplace that already has reputation data to protect buyers with.
