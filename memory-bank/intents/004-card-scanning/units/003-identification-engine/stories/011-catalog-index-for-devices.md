---
id: 011-catalog-index-for-devices
unit: 003-identification-engine
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T13:50:00Z'
assigned_bolt: 020-identification-ladder
implemented: false
---

# Story: 011-catalog-index-for-devices

## User Story

**As** a collector standing in a card shop with one bar of signal
**I want** the catalog to already be on my phone
**So that** the scanner works where I actually use it, rather than only where the network is good

## Acceptance Criteria

- [ ] **Given** the catalog, **When** the index is built, **Then** it contains what text matching needs
      — card name, collector number, set code, printing attributes — and nothing it does not
- [ ] **Given** the index, **When** its size is measured, **Then** it is ≤ 8MB for the full catalog
- [ ] **Given** a device with an older index, **When** it updates, **Then** it fetches a **delta**
      rather than the whole index
- [ ] **Given** a device, **When** its index version is older than the current one, **Then** the
      staleness is detected and refreshed — a stale index is never used silently
- [ ] **Given** a device with no network, **When** a scan runs, **Then** the last downloaded index is
      used and the result states which index version produced it
- [ ] **Given** the index endpoint, **When** it is called, **Then** the response is cacheable and
      versioned, so a thousand devices refreshing cost one build

## Technical Notes

The index is a projection of the catalog, not a copy: no rules text, no flavour text, no artist, no
image URL. Those are what make the catalog large and none of them help identify a card from a
photograph.

Versioning is monotonic and the delta is computed against a known prior version. A device more than
`n` versions behind takes the full index rather than chaining deltas — chained deltas are a category of
bug that only appears in the field.

**Why staleness must be loud.** A device holding an index from before a set was added will report
`no_catalog_match` for every card in that set, and the failure is indistinguishable from OCR failure
unless the index version travels with the result. That is why the sixth criterion in story 016's
taxonomy and the fifth here are the same fact seen from two ends.

## Dependencies

### Requires
- 001-compile-pilot-set
- 005-scan-api-skeleton

### Enables
- 012-on-device-text-pass
- 031-offline-collection-cache — different data, same update discipline

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| The catalog grows past 8MB of index | Compression and field pruning first; if it still does not fit, the index becomes per-set-group with on-demand fetch. Recorded as a decision, not silently exceeded |
| A device has never downloaded an index | First launch fetches it before offering the scanner, with an honest progress state |
| The delta is larger than the full index | Serve the full index. This happens after a bulk import and is a normal case |
| Index build runs while a scan is in flight | The scan completes against the version it started with; versions are immutable once published |

## Out of Scope

- Matching against the index (story 012)
- The catalog itself (unit 001)
