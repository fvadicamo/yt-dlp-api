# Test mode with a mock yt-dlp executor as the e2e strategy

- Status: accepted
- Date: 2025-12-25 (reconstructed 2026-07-12)

## Context

Real YouTube calls in CI are flaky, rate-limited and require cookies.
End-to-end coverage of the API surface still matters.

## Decision

`APP_TESTING_TEST_MODE=true` routes provider execution to a
`MockYtdlpExecutor` returning deterministic demo data (videos, formats,
downloads, captions). E2e tests and the container smoke test run the full
app against the mock; startup checks relax only what the mock replaces.

## Consequences

- CI exercises the whole stack (auth, queue, worker, storage) hermetically
- The mock must track new yt-dlp interactions (e.g. transcript commands)
- Real-YouTube behavior is validated manually or in production monitoring
