---
id: 005-platform-log-forwarding
unit: 001-platform-foundation
intent: 001-collection-tracker
status: ready
priority: must
created: 2026-08-09T12:00:00Z
assigned_bolt: 001-platform-foundation
implemented: false
---

# Story: 005-platform-log-forwarding

## Description

`log_event()` additionally forwards `error`, `critical` and every `security`-category entry to logs-api over the M2M account, marking `forwarded_to_platform`.

## Rationale

The platform console is the single operational pane across every app. Local-only logs mean an outage here is invisible where the operator is actually looking.

## Acceptance Criteria

- [ ] **Given** an error or security event is logged, **When** forwarding runs, **Then** it appears in the platform console within a minute
- [ ] **Given** forwarding is in flight, **When** the request completes, **Then** the user was never blocked on it — it is asynchronous and best-effort
- [ ] **Given** logs-api is stopped, **When** requests are served, **Then** they still succeed and `app_logs` still records everything
- [ ] **Given** the forward buffer fills, **When** the bound is reached, **Then** entries are dropped with a counter rather than growing without end
- [ ] **Given** any code logs anything, **When** reviewed, **Then** no call site chooses a destination — the routing rule exists only inside `log_event()`

## Technical Notes

- Scope required on the M2M role: `logs:write`.
- One call site, two destinations. This is the whole design: the rule can change once, in one function, rather than being re-decided at every log statement.

## Dependencies

### Requires
- 004-app-logging

### Enables
- Operational visibility for the whole intent

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| logs-api returns 403 | Scope missing — surface loudly at startup, not silently at runtime |
| logs-api slow | Bounded timeout, then buffer; never extend a user request |
| Burst of 10k errors | Rate-limited and coalesced; the buffer bound protects memory |

## Out of Scope

- Usage metering — 006
