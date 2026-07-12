# In-memory job queue and store with TTL, no external broker

- Status: accepted
- Date: 2025-12-20 (reconstructed 2026-07-12)

## Context

Async downloads need job tracking, prioritization and concurrency limits.
Redis/RabbitMQ would add operational surface for a single-container
deployment target.

## Decision

In-process priority queue + job store with 24h TTL and slot-based
concurrency control; jobs survive within the process lifetime only.
Webhooks (v0.2.0) mitigate the polling cost for consumers.

## Consequences

- Zero external dependencies; single-container deployment stays trivial
- Restart loses queue state: consumers must handle job disappearance
  (documented; webhook `job.failed` is not emitted on restart)
- Horizontal scaling needs sticky consumers or a future broker adapter
