---
id: 004-app-logging
unit: 001-platform-foundation
intent: 001-collection-tracker
status: ready
priority: must
created: 2026-08-09T12:00:00Z
assigned_bolt: 001-platform-foundation
implemented: false
---

# Story: 004-app-logging

## Description

A `log_event()` helper writing every notable event to `elestrals.app_logs`, plus a logged-route wrapper recording one row per request.

## Rationale

You asked for our own logging table, and it is the only log store we can join against our own domain — reading a scraper failure next to the run it belongs to is worth more than reading it in a generic console.

## Acceptance Criteria

- [ ] **Given** any request completes, **When** it is logged, **Then** exactly one `app_logs` row exists with method, route, status, duration, `request_id` and `user_sub`
- [ ] **Given** an unhandled exception escapes, **When** it is caught, **Then** a `critical` row is written with a trace
- [ ] **Given** a request carries an `Authorization` header or a secret-shaped key, **When** the row is written, **Then** those values are redacted **before** persistence — including inside request-validation error payloads
- [ ] **Given** application code emits a manual entry, **When** it is called, **Then** `debug`/`info`/`warning`/`error`/`critical` are all available
- [ ] **Given** logging is enabled, **When** latency is measured, **Then** it adds under 3ms p95
- [ ] **Given** the retention sweep runs, **When** it completes, **Then** `debug`/`info` older than 30 days and `warning`+ older than 365 days are gone

## Technical Notes

- `app_logs` deliberately mirrors the platform's `application_logs` shape so it is recognisable to anyone who knows the auth repo, plus `user_sub` and `request_id` for joining against our tables.
- Redaction happens before persistence, not before display. A redacted-on-read design leaks the moment someone queries the table directly.

## Dependencies

### Requires
- None — infrastructure

### Enables
- 005-platform-log-forwarding
- Every story: this is how they are diagnosed

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Log write itself fails | Swallowed and counted; a logging failure must never fail a user request |
| Enormous exception payload | Trace truncated to a bounded length with a marker |
| Request with no authenticated user | `user_sub` is null, everything else still recorded |

## Out of Scope

- Forwarding to logs-api — 005
