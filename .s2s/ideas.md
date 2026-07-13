# yt-dlp-api Ideas

**Updated**: 2026-07-11
**Format**: Structured ideas from brainstorm sessions and manual entries

---

## ID Conventions

| Prefix | Category | Example |
|--------|----------|---------|
| IDEA | Ideas and concepts | IDEA-001 |

**Status values**: `draft` | `validated` | `promoted` | `parked` | `rejected`

---

## Active

### IDEA-002: Pluggable external transcription contract

**Status**: promoted | **Created**: 2026-07-11 | **Promoted**: 2026-07-13
**Origin**: manual
**Promoted to**: FEAT-004 (planned, gated on a concrete consumer)

**Problem**: Subtitles/auto-captions (FEAT-002) cover most videos, but some
have none, and dedicated STT pipelines (GPU whisper-class models, diarization)
produce better transcripts. The API should enable them without embedding ML.

**Solution outline**: Keep the core lean: audio extraction (exists) + job
webhooks (FEAT-003) already let an external pipeline pick up completed audio
and transcribe it. If demand emerges, add a documented callback contract
(`POST audio -> transcript`) so a config-declared external STT service can
back the transcript endpoint when captions are missing.

**Next**: Ship FEAT-002/003 first; revisit after real-world usage.

---

## Parked

### IDEA-001: Additional providers via existing abstraction

**Status**: parked | **Created**: 2026-07-11 | **Parked**: 2026-07-11
**Origin**: manual
**Reason**: demand-driven; YouTube covers current users

**Problem**: yt-dlp supports hundreds of sites; the API only ships YouTube.

**Solution outline**: `VideoProvider` ABC + `ProviderManager` already isolate
providers. Add e.g. Vimeo/Twitch as config-enabled providers with their own
cookie slots and URL validators.

**Revisit when**: a GitHub Discussion/issue shows concrete demand.

### IDEA-003: Generated API clients (Python/TypeScript)

**Status**: parked | **Created**: 2026-07-11 | **Parked**: 2026-07-11
**Origin**: manual
**Reason**: OpenAPI spec is already exposed; generation adds maintenance

**Problem**: Consumers hand-write HTTP calls.

**Solution outline**: Publish generated clients from `/openapi.json` (e.g.
openapi-python-client, openapi-typescript) as part of releases.

**Revisit when**: external users ask for SDKs.

### IDEA-004: Helm chart

**Status**: parked | **Created**: 2026-07-11 | **Parked**: 2026-07-11
**Origin**: manual
**Reason**: DEPLOYMENT.md already has raw k8s manifests; charts imply upkeep

**Problem**: Kubernetes users must adapt raw manifests.

**Solution outline**: `charts/` with values for keys, cookies secret,
persistence, resources; publish via GitHub Pages OCI registry.

**Revisit when**: k8s adoption signals appear (issues/discussions).

### IDEA-006: Dynamic provider plugin loading (requirement 36)

**Status**: parked | **Created**: 2026-07-11 | **Parked**: 2026-07-11
**Origin**: `.kiro` requirement 36, never implemented
**Reason**: no external plugin authors yet; abstraction suffices

**Problem**: Requirement 36 envisioned loading provider plugins from a
directory without modifying core code; current registration is hardcoded in
`app/main.py`.

**Solution outline**: entry-point or directory-based discovery with interface
validation and error isolation, building on `ProviderManager`.

**Revisit when**: IDEA-001 lands a second provider and a third-party asks to
ship one out-of-tree.

---

## Promoted

### IDEA-005: Transcript extraction and push notifications as differentiators

**Status**: promoted | **Created**: 2026-07-11 | **Promoted**: 2026-07-11
**Origin**: manual (production readiness analysis)
**Promoted to**: FEAT-002, FEAT-003

**Problem**: Existing OSS yt-dlp wrappers stop at download/metadata; pipeline
consumers need transcripts-as-data and push semantics.

**Solution outline**: transcript endpoint backed by subtitles/auto-captions;
HMAC-signed job completion webhooks with SSRF-safe allowlist.

---

## Rejected

### IDEA-007: Bundled web UI

**Status**: rejected | **Created**: 2026-07-11 | **Rejected**: 2026-07-11
**Origin**: manual
**Reason**: API-first scope; MeTube and similar projects already own the
self-hosted UI niche. A UI would dilute the "reference API" positioning.

**Problem**: Some users want a browser interface.

**Solution outline**: n/a; document UI alternatives in README instead.
