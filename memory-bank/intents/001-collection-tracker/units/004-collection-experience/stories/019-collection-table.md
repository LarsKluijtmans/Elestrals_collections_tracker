---
id: 019-collection-table
unit: 004-collection-experience
intent: 001-collection-tracker
status: ready
priority: must
created: 2026-08-09T12:00:00Z
assigned_bolt: 006-collection-browse
implemented: false
---

# Story: 019-collection-table

## User Story

**As a** collector
**I want** one table containing everything I own
**So that** I can find any card and understand my collection at a glance

## Acceptance Criteria

- [ ] **Given** I own 10,000 holdings, **When** I scroll the table, **Then** it sustains 60fps on a mid-range laptop and the API responds in under 400ms p95
- [ ] **Given** the table renders, **When** I look at a row, **Then** I see thumbnail, name, set, element chip, rarity, condition badge, quantity stepper and date added
- [ ] **Given** I click a column header, **When** it sorts, **Then** the sort is reflected in the URL and survives a reload
- [ ] **Given** I toggle density, **When** it switches between comfortable (56px) and compact (36px), **Then** the choice persists across sessions
- [ ] **Given** images are still loading, **When** the table paints, **Then** skeletons occupy the exact final dimensions and nothing reflows
- [ ] **Given** I change a quantity with the stepper, **When** the change is in flight, **Then** the new value shows immediately and reverts **visibly** if the server rejects it
- [ ] **Given** I own nothing, **When** I open the page, **Then** I get a written empty state with one clear action — not an empty grid
- [ ] **Given** I use a keyboard only, **When** I tab through the table, **Then** every stepper and row action is reachable with a visible focus ring
- [ ] **Given** `prefers-reduced-motion` is set, **When** the table renders, **Then** foil sheen and row animation are suppressed

## Technical Notes

- TanStack Table for the model, TanStack Virtual for windowing. Row height must be known ahead of
  render for both density modes — variable-height virtualization is what makes these tables stutter.
- Server-side pagination with a cursor, not an offset. `OFFSET 9000` degrades exactly where the
  10,000-row target lives.
- The quantity stepper is the most-used control in the product: 44px hit target, 400ms debounce so a
  held key produces one request rather than twenty, and optimistic with visible revert.
- Element chips are the hue at 14% alpha with full-strength text and border, and always carry the
  element name. Never a solid fill — solid saturation is reserved for the brand accent.
- Rarity is a material (flat / ring / gradient / iridescent border), never a hue. Element already
  owns hue, and two hue encodings in one row is unreadable.
- Condition is a neutral badge with a letter grade. No colour.
- Thumbnails are lazy-loaded with `loading="lazy"` and a fixed aspect-ratio box.

## Dependencies

### Requires
- 013-add-inventory-item (something to list)
- 012-card-detail (rows link into it)
- 020-collection-filters (ships together; the table is not useful unfiltered at 10k rows)

### Enables
- 021-saved-views
- 022-bulk-actions
- Phase 2: the value and delta columns attach to this table

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| 10,000 rows, all filters cleared | Virtualized, cursor-paged, still 60fps |
| A printing whose image URL 404s | Placeholder art with the card name; never a broken-image icon |
| Very long card name | Truncated with an ellipsis and a title tooltip; the row height does not change |
| Quantity stepper held down | One debounced request, correct final value |
| Two tabs open, one edits | The stale tab reconciles on refetch rather than overwriting |
| A row is deleted in another tab | Refetch removes it; acting on it returns 404, handled as a calm inline message |
| Narrow viewport (<900px) | Columns collapse to a two-line card row; the stepper stays reachable |

## Out of Scope

- Price and delta columns — intent 002 adds them to this same table
- Bulk selection behaviour — `022-bulk-actions`
- Filter construction — `020-collection-filters`
