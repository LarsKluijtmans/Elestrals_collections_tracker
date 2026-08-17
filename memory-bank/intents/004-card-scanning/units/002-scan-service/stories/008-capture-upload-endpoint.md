---
id: 008-capture-upload-endpoint
unit: 002-scan-service
intent: 004-card-scanning
status: ready
priority: must
created: '2026-08-17T13:43:00Z'
assigned_bolt: 019-scan-service-foundation
implemented: false
---

# Story: 008-capture-upload-endpoint

## User Story

**As** the operator of a service that now accepts arbitrary binary from the internet
**I want** an upload path that trusts nothing the client claims
**So that** the first user-generated binary in this project does not also become its first remote
code execution

## Acceptance Criteria

- [ ] **Given** an upload, **When** it arrives, **Then** content type, magic bytes, dimensions and byte
      size are all validated, and a mismatch between declared and actual type is rejected
- [ ] **Given** a valid image, **When** it is stored, **Then** it has been **decoded and re-encoded**
      server-side — the bytes on disk are ours, not the client's
- [ ] **Given** an upload, **When** EXIF is checked, **Then** its absence is **verified server-side**;
      a payload arriving with EXIF is stripped rather than trusted or refused, and the occurrence is
      counted
- [ ] **Given** an upload, **When** GPS data is present anywhere, **Then** it is removed
      unconditionally and never persisted, not even transiently to disk
- [ ] **Given** an upload exceeding the size or dimension budget, **When** it arrives, **Then** it is
      rejected with a clear reason rather than silently downscaled
- [ ] **Given** an upload, **When** the caller has no valid platform JWT, **Then** it is refused before
      any bytes are read
- [ ] **Given** an authenticated caller, **When** they upload at an abusive rate, **Then** a per-user
      rate limit applies

## Technical Notes

This endpoint is the largest new attack surface this project has ever added, and it is worth naming
that plainly. Everything before it accepted JSON.

**The client's crop is a privacy feature; the server's validation is the security boundary.** Story
033 crops on the device so the room never leaves the phone. This story assumes that could have been
bypassed, because it could: a modified client can post whatever it likes. So the server re-encodes
regardless, which incidentally strips metadata as a side effect of decoding and re-encoding rather
than as a bespoke step that might be skipped.

Decode with a hard pixel-count ceiling to refuse decompression bombs — an image that is small on the
wire and enormous in memory is the classic form of this attack.

Rate limiting is per `user_sub`, not per IP. The threat model here is a signed-in account filling
storage, not an anonymous flood.

## Dependencies

### Requires
- 007-capture-store

### Enables
- 013-identification-ladder — pass 2 uploads through this endpoint
- 033-capture-and-crop — the client half of the same contract

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| A polyglot file that is a valid image and a valid archive | Re-encoding discards everything that is not pixels, which is the point of re-encoding rather than passing bytes through |
| An image with an enormous declared canvas | Refused at the pixel-count ceiling before allocation |
| EXIF arrives despite the client contract | Stripped, counted, and the count surfaced — a rising count means a client build has regressed |
| Storage is unavailable | The upload fails cleanly and the ladder degrades to the on-device pass; a scan must never be blocked by the corpus being unwritable |
| The user has not accepted the current consent version | Refused with a reason the client can act on, per story 024 |

## Out of Scope

- Cropping (story 033)
- Deciding whether the image is any good (unit 005)
- Fingerprinting it (story 009)
