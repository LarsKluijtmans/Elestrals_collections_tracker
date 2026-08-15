---
id: 016-fast-add-flow
unit: 004-collection-experience
intent: 001-collection-tracker
status: ready
priority: must
created: 2026-08-09T12:00:00Z
assigned_bolt: 005-collection-entry
implemented: false
---

# Story: 016-fast-add-flow

## User Story

**As a** collector with a 400-card box on the desk
**I want** to enter cards without my hands leaving the keyboard
**So that** cataloguing a box takes an evening rather than a weekend

## Acceptance Criteria

- [ ] **Given** I am on `/collection/add` with the page freshly loaded, **When** it renders, **Then** focus is already in the search field — I never have to click to start
- [ ] **Given** focus is in the search field, **When** I type three characters, **Then** ranked results appear in under 150ms and the first result is highlighted
- [ ] **Given** results are showing, **When** I press `↓`/`↑`, **Then** the highlight moves; **When** I press `Enter`, **Then** the highlighted printing is added, the field clears, and focus returns to it
- [ ] **Given** I added a card with condition Near Mint and finish Foil, **When** I add the next card, **Then** Near Mint and Foil are still selected — the settings carry forward
- [ ] **Given** I want to change condition mid-session, **When** I press the condition shortcut, **Then** I can change it without leaving the keyboard, and the new value carries forward from then on
- [ ] **Given** I have added several cards, **When** I look at the session tally, **Then** I see the total count and the last five adds in reverse order
- [ ] **Given** an add fails on the server, **When** the optimistic row is rolled back, **Then** I see an inline, non-blocking message naming the card that failed — the failure is never silent
- [ ] **Given** a screen reader is active, **When** an add succeeds or fails, **Then** it is announced via a live region
- [ ] **Given** a first-time user with a stack of cards, **When** they are timed, **Then** the median single-add interaction is under 5 seconds and 100 cards take under 10 minutes

## Technical Notes

- **This is the single interaction the product is judged on.** A collector who finds it slow does
  not come back, and no other feature compensates.
- Optimistic mutation via TanStack Query `onMutate` with rollback in `onError`. The optimistic row
  appears in the tally instantly; the network round-trip must never gate the next keystroke.
- Adds are fired concurrently, not queued — which is exactly why 013 requires the upsert to be
  atomic rather than read-then-write.
- Debounce search at ~120ms. Cancel in-flight searches on a new keystroke so a slow earlier response
  cannot overwrite a newer result set.
- Carry-forward state (condition, finish, language, edition) lives in the add-session context, not
  the URL, and resets on navigation away.
- Default the printing selection to the most common one for that card, so the common case is
  `type → Enter` with no arrowing at all.
- Keyboard map: `Enter` add · `↑`/`↓` navigate · `Esc` clear field · `Ctrl/Cmd+Z` undo last add when
  the field is empty · `Alt+C` condition · `Alt+F` finish.

## Dependencies

### Requires
- 010-card-search
- 013-add-inventory-item
- 018-undo-recent-adds (for the `Ctrl+Z` binding; the flow ships without it if 018 slips)

### Enables
- 017-set-grid-entry (shares the session state)
- Meaningful data for 019-collection-table to display

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| `Enter` pressed with no results | Nothing happens; field keeps focus, no error flash |
| `Enter` pressed while the search is still in flight | Wait for the result, then act on the highlighted row — never add the wrong card |
| Network drops mid-session | Adds queue in memory, the UI shows an offline indicator, and the queue flushes on reconnect |
| The same card added 12 times rapidly | One row, quantity 12 |
| Card has only one printing | It is preselected; `type → Enter` is the whole interaction |
| Card has 6 printings | The most common is preselected and the list is arrow-navigable |
| User pastes a 40-character string | Search handles it; no results is a calm empty state, not an error |
| Browser autofill fires on the search field | Suppressed with `autocomplete="off"` — an autofilled address in a card search is pure noise |

## Out of Scope

- Grid entry (`017-set-grid-entry`)
- CSV import (`unit 006`)
- Scanning cards with a camera — an obvious future idea, deliberately not phase 1
