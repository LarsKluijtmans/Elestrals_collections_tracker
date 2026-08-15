---
id: 026-run-history-and-health
unit: 005-admin-console
intent: 002-price-intelligence
status: ready
priority: must
created: 2026-08-15T15:00:00Z
assigned_bolt: 013-admin-console-core
implemented: false
---

# Story: 026-run-history-and-health

## User Story

**As an** admin
**I want** to see how each source is doing
**So that** I can tell the difference between a healthy pipeline finding a quiet market and a broken
one finding nothing

## Acceptance Criteria

- [ ] **Given** each configured source, **When** I open the health view, **Then** I see its last run
      per mode, duration, status, and every counter — queries, fetched, parsed, accepted, rejected,
      discovered, ended
- [ ] **Given** a source's history, **When** I view it, **Then** I see the accept rate as a trend
      over time, not only its latest value
- [ ] **Given** a quarantined source, **When** I view it, **Then** it is visibly distinct from a
      healthy one and shows when it will next be retried
- [ ] **Given** a source that has never run, **When** I view it, **Then** it says so, distinctly from
      one whose last run found nothing
- [ ] **Given** each source, **When** I view it, **Then** its terms-review note and its risk owner
      are shown next to its name
- [ ] **Given** a source, **When** I use its kill switch, **Then** it is disabled and the next scan
      does not run, with no deploy
- [ ] **Given** a sustained drop in accept rate, **When** it crosses the threshold, **Then** an alert
      is raised through the phase-1 logging path
- [ ] **Given** a failed or partial run, **When** I open it, **Then** its `error_summary` is readable
      in full

## Technical Notes

The distinction in the user story is the whole point. Under ADR-004 a connector *will* break when a
site changes markup, and the failure is silent: zero rows looks exactly like a quiet market. Three
things separate them, and this story shows all three — the accept-rate trend, the quarantine state,
and the drift check from story 010.

Showing the terms note and the risk owner next to the source name is deliberate. ADR-004 accepts a
risk per source; putting the accepted text where an admin sees it every time they look at the
pipeline is what keeps "reviewed: yes" from being enough.

The kill switch writes `enabled = 0`. Enabling is **not** available here — see the unit brief:
accepting a risk is a deliberate act with a written note, not a toggle.

## Dependencies

### Requires
- 024-admin-shell-and-routing
- 005-run-lifecycle-and-sweeper — the runs and counters it reads
- 011-block-detection-and-quarantine — the quarantine state it shows

### Enables
- 027-trigger-and-watch-a-scan
- 028-coverage-and-match-quality

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| A run is currently in progress | Shown as running with live counters (story 027 owns the live view) |
| A run was swept to failed | Shown as failed with the sweeper's explanation, not as an ordinary failure |
| Accept rate is 0% because the catalog is empty | The empty-catalog failure from story 008 appears in `error_summary`, so the cause is visible rather than inferred |
| A source has an orphaned config row with no connector | Listed as orphaned rather than omitted |
| Two modes with very different accept rates | Trended separately. A deep scan's rate is legitimately lower than a light scan's, and merging them hides both |

## Out of Scope

- Starting or stopping a run (story 027)
- Enabling a source or editing its terms review
