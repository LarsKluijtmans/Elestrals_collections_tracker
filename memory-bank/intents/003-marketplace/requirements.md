---
intent: 003-marketplace
phase: inception
status: outline
created: 2026-08-09T12:00:00Z
updated: 2026-08-09T12:00:00Z
---

# Requirements: Marketplace (outline)

> **Status: deliberately an outline.** The commercial model is undecided, and it is the single
> decision that determines the size, cost and legal exposure of this intent. Everything below is
> structured so that either route can be taken **without a data migration** — phase 1 already
> shapes `listings`, `orders`, `order_items` and `order_events` to accept a payment service
> provider as an addition rather than a rewrite.
>
> This intent is elaborated to full requirements once that decision is made.

## Intent Overview

Let collectors sell to each other on the site, with the price guidance from intent 002 present at
the moment of decision — the thing no general marketplace can offer, because none of them know what
is in your collection or what it is worth.

## The decision that gates everything

| | **Route A — listings only** | **Route B — payments + escrow** |
|---|---|---|
| What we do | list, browse, message, agree | take payment, hold, release, take a fee |
| Money | between users, off-platform | through a PSP (Stripe Connect / Mollie) |
| Revenue | none directly (subscription or promotion instead) | commission per completed order |
| Seller onboarding | a handle | KYC/AML identity verification |
| We must build | listings, search, chat, reputation, reporting | all of route A **plus** payments, escrow, refunds, disputes, payouts, chargebacks, tax reporting |
| Legal exposure | low — we are a noticeboard | high — we are a payment intermediary and likely a regulated one |
| Rough size | ~4 units, comparable to intent 001 | ~7 units, larger than intents 001 and 002 combined |
| Reversible? | yes — route B is a later addition | no — regulatory obligations do not switch off |

**Recommendation, for when the decision is taken:** start with route A, and treat the first 6 months
of listing volume as the evidence for whether route B is worth its cost. Route A also produces the
reputation history that makes route B safe to launch, and it does not foreclose anything.

## Provisional Functional Requirements

### FR-1: Create a listing from inventory
Sell what you already track. Prefilled printing, condition and photos; a suggested price drawn from
`price_daily` with its confidence shown. Listing a card reserves it against the holding so the same
copy cannot be listed twice.

### FR-2: Browse and search listings
Filters mirroring `/collection` — set, element, rarity, condition, finish, language. Each result
shows price **against market**: "€24 · 12% below 30-day median (high confidence)". This is the
feature that justifies the marketplace existing here rather than elsewhere.

### FR-3: Messaging
Per-listing conversations between buyer and seller. Rate-limited, reportable, and retained for
dispute reconstruction.

### FR-4: Orders
An order captures agreed items and prices **by copy, not by reference** — a later listing edit must
never rewrite history. Status is a projection of the append-only `order_events` log, so any dispute
can be reconstructed exactly.

### FR-5: Reputation
One rating per completed order, only from a completed order. Reputation that cannot be manufactured
is the entire point; anything weaker is worse than nothing because it looks like a signal.

### FR-6: Trust and safety
Report a listing or a user; an operator queue; takedowns; suspension. Counterfeit reporting matters
specifically in a TCG marketplace and needs its own report reason and workflow.

### FR-7 (route B only): Payments, escrow, payouts
PSP onboarding, seller KYC/AML, hold-and-release, refunds, chargebacks, dispute resolution, payout
scheduling, and tax reporting. Each of these is a unit in itself, not a story.

## Non-Functional (provisional)

| Area | Requirement |
|---|---|
| Trust | A price-versus-market verdict on every listing, always with its confidence |
| Abuse | Rate limits on listing creation and messaging; new-account limits |
| Privacy | Sellers expose a handle and reputation, never an email — contact stays in-platform |
| Auditability | `order_events` is append-only; order status is derived, never set directly |
| Legal | Marketplace terms, a counterfeit policy, and (route B) regulatory registration |

## Constraints

- **Payment-agnostic until decided.** The `orders` status machine already reserves
  `payment_pending`, `paid` and `refunded`. They stay unused under route A.
- No listing may exceed the quantity actually held.
- Prices in `order_items` are copies, never foreign keys to a mutable listing price.
- Photos are end-user `owned` files in storage-api, carried by the user's own token.

## Open Questions — all blocking full elaboration

| Question | Owner | Blocking |
|---|---|---|
| **Route A or route B?** | Lars | Everything |
| If B: which PSP, and does it support marketplace/split payouts in our jurisdictions? | Lars | Units 5–7 |
| If B: what registration or licence does acting as a payment intermediary require? | Lars + legal | Whether B is viable at all |
| Do we have permission to run a commercial marketplace around this trademark? | Lars | Public launch of this intent |
| Does displaying aggregated price data commercially need a licence from any source? | Lars | Also affects intent 002 |
| Domestic only, or cross-border shipping and VAT? | Lars | Order model, tax handling |

## What phase 1 already does for this intent

Recorded here so it is not rebuilt: `user_profiles.handle`, `inventory_items.is_for_trade`, the
storage-api photo path, the notification outbox, the `listings`/`orders`/`order_items`/
`order_events` shapes in `standards/data-model.md`, and `/u/:handle` as the public profile that
becomes the seller profile.
