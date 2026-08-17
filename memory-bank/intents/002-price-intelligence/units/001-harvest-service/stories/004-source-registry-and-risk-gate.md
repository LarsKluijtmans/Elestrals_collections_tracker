---
id: 004-source-registry-and-risk-gate
unit: 001-harvest-service
intent: 002-price-intelligence
status: ready
priority: must
created: 2026-08-15T15:00:00Z
assigned_bolt: 010-harvest-service-foundation
implemented: false
---

# Story: 004-source-registry-and-risk-gate

## User Story

**As the** person who carries the risk of this pipeline
**I want** a source to be unable to run until someone has read its terms and put their name to
accepting them
**So that** the risk ADR-004 takes on is one that was actually read, per source, rather than one
that was assumed once and never revisited

## Acceptance Criteria

- [ ] **Given** a source row, **When** `tos_review_note` is empty and someone sets `enabled = 1`,
      **Then** the database refuses the write via a CHECK constraint
- [ ] **Given** a source row, **When** `risk_accepted_by` is null and someone sets `enabled = 1`,
      **Then** the database refuses it the same way
- [ ] **Given** an enabled source, **When** a scan starts, **Then** the gate re-checks it in Python
      before any outbound request and refuses with a message naming the fix
- [ ] **Given** a source whose declared host is not on the outbound allowlist, **When** a scan
      starts, **Then** it is refused — the harvester cannot be steered to an arbitrary host
- [ ] **Given** an adapter declaring one access mode and a config row declaring another, **When** a
      scan starts, **Then** it is refused rather than one of the two being preferred
- [ ] **Given** a source set `enabled = 0`, **When** the next scan is scheduled, **Then** it does not
      run, with no deploy and no restart
- [ ] **Given** the registry, **When** a new connector is added, **Then** it takes one adapter file
      and one config row, and nothing else in the codebase learns the source's name

## Technical Notes

`price_sources` carries `tos_review_note TEXT`, `risk_accepted_by VARCHAR(128)` and
`risk_accepted_on DATE`. The constraint:

```sql
CHECK (enabled = 0 OR (tos_review_note IS NOT NULL AND risk_accepted_by IS NOT NULL))
```

MySQL has enforced CHECK since 8.0.16 and SQLite always has, so it holds on both the production and
the unit-test path.

**The note is prose on purpose.** A boolean `reviewed` flag records that someone clicked something.
The note has to say what the terms actually say — including, for at least two sources, that they
prohibit this — because ADR-004 accepts a risk, and a risk you have not articulated is one you have
not accepted.

The gate **raises**; it does not return a boolean. A caller who forgets to check a return value
makes a request anyway.

Enabling is deliberately not a UI action (unit 005 scope note): it happens in a migration or a CLI
command that requires the note as an argument.

## Dependencies

### Requires
- 002-harvest-schema-and-grants

### Enables
- 006-rate-limiting-and-identification
- 007-source-connector-contract
- 011-block-detection-and-quarantine — quarantine is a second reason the gate refuses
- 026-run-history-and-health — the console displays this row's state

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| A registered connector has no config row | Refused, with "insert the row with its terms review first" |
| A config row has no registered connector | Visible as an orphan in the console and the CLI listing, not silently ignored |
| Someone writes "reviewed: yes" as the note | The constraint passes. This is a social control, not a technical one, and the ADR says so — the mitigation is that the note is displayed in the console next to the source's name |
| Terms change after acceptance | Not detectable automatically. ADR-004's review triggers cover it, and the annual re-review is a follow-up |
| A source is quarantined | The gate refuses it for as long as the quarantine lasts (story 011) |

## Out of Scope

- Editing the review or the risk owner from the admin UI — deliberately excluded in the unit brief
- Any per-source connector logic (unit 002)
