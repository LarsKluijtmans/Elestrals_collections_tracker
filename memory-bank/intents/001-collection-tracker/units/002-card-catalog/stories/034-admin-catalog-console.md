---
id: 034-admin-catalog-console
unit: 002-card-catalog
intent: 001-collection-tracker
status: ready
priority: should
created: 2026-08-09T12:00:00Z
assigned_bolt: 003-card-catalog-surface
implemented: false
---

# Story: 034-admin-catalog-console

## User Story

**As a** operator
**I want** to see catalog health
**So that** I know whether the data users depend on is current and complete

## Acceptance Criteria

- [ ] **Given** I open `/admin/catalog`, **Then** I see the last run per source with status, counts and duration
- [ ] **Given** a set's data is older than 30 days, **Then** it is flagged as stale
- [ ] **Given** rows were rejected, **Then** they list with reasons and a link to the source record
- [ ] **Given** I need fresh data, **When** I trigger a re-run per source, **Then** it starts and appears as a running row
- [ ] **Given** I am not an operator, **When** I request the page, **Then** I get 403; unauthenticated gets 401

## Technical Notes

- RBAC is the platform's, checked server-side. The browser cannot assert its own privilege.

## Dependencies

### Requires
- 009-import-run-reporting

### Enables
- Operational confidence before launch

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| No runs yet | Empty state explaining how to trigger the first import |
| Re-run triggered while one is running | Rejected with a message naming the running run |

## Out of Scope

- Editing catalog data by hand — the importer is the only writer
