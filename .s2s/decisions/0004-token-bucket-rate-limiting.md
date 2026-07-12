# Per-API-key token bucket rate limiting by endpoint category

- Status: accepted
- Date: 2025-12-18 (reconstructed 2026-07-12)

## Context

Metadata calls are cheap; downloads are expensive and abuse-prone. Limits
must apply per consumer without external infrastructure.

## Decision

In-memory token buckets per (api_key, category) with categories mapped from
paths (metadata: info/formats/transcript; download: download), burst
capacity, Retry-After on 429, and a bounded key map against memory DoS.

## Consequences

- No shared state across replicas (consistent with ADR-0003 single-node scope)
- New endpoints must be added to ENDPOINT_CATEGORIES explicitly
