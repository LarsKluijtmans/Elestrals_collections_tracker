---
intent: 004-card-scanning
phase: inception
status: in-progress
created: 2026-08-17T10:00:00Z
completed: null
---

# Inception Log: 004-card-scanning

## Overview

**Intent**: Identify a physical Elestrals card from a camera image, on a new mobile app and in the
existing web app, and record ownership from the result.
**Type**: brown-field — new capability on top of the phase-1 catalog and inventory, plus one
genuinely green-field piece (the mobile client, which does not exist today).
**Created**: 2026-08-17

## Session 1 — 2026-08-17 — intent created

Requested as: *"a mobile app and a feature in the website for scanning cards and identifying them, so
that a user can scan their card, the app shows them which one it is and they can redirect to that
card, and note how many they have."*

Two deliverables, one capability: the identification engine is shared, the surfaces differ.

Read before drafting: `project.yaml`, `standards/tech-stack.md`, `standards/data-model.md`
(catalog and inventory sections), intents 001 (units and decomposition), 002 (requirements, for the
house pattern of spike-first on an unknown), 003 (outline, for scope overlap).

### Numbering

Allocated `004` rather than inserting ahead of `003-marketplace`, because `003` is referenced from
`project.yaml`, `standards/data-model.md` and `decision-index.md`, and renumbering it buys nothing.
Folder number is allocation order; the `phase` field carries intended shipping order and is set at
Checkpoint 2.

### Two constraints found in the existing standards that shape the intent

1. **`printings` is the SKU, and a camera cannot see all of it.** A photograph identifies a card
   face. Rarity is often visually inferable, finish sometimes, edition and language sometimes, but not
   reliably enough to write an inventory row unattended. The design gap between "which card" and
   "which printing" is the first real problem this intent has.
2. **The catalog holds image *URLs*, never bytes** — deliberately, pending permission from the rights
   holder. A server-side visual matcher needs a reference corpus derived from those images. That is
   the same class of question ADR-004 answered for scraping, and it likely needs its own ADR.

### Checkpoint 1 — Clarifying questions

Put to the user before any requirement was written. Four decision forks, plus follow-ups.

| # | Question | Answer |
|---|---|---|
| 1 | How is the mobile client built? | *pending* |
| 2 | How is a card recognised? | *pending* |
| 3 | What does a scan resolve to? | *pending* |
| 4 | Scanner companion, or full second client? | *pending* |

## Artifacts Created

| Artifact | Status | File |
|----------|--------|------|
| Requirements | draft (goal + scope) | `requirements.md` |
| Inception Log | in progress | `inception-log.md` |
| System Context | — | not started |
| Units | — | not started |
| Stories | — | not started |
| Bolt Plan | — | not started |

## Decision Log

| Date | Decision | Rationale | Approved |
|------|----------|-----------|----------|
| 2026-08-17 | Intent numbered `004`, not inserted before marketplace | `003` is referenced from three standards files; folder number is allocation order, `phase` carries shipping order | Yes |

## Scope Changes

| Date | Change | Reason | Impact |
|------|--------|--------|--------|

## Ready for Construction

**Checklist**:
- [ ] All requirements documented
- [ ] System context defined
- [ ] Units decomposed
- [ ] Stories created for all units
- [ ] Bolts planned
- [ ] Human review complete

## Next Steps

1. Answer Checkpoint 1 questions
2. Generate full requirements (Checkpoint 2)
3. Generate context + units + stories + bolt plan (Checkpoint 3)
