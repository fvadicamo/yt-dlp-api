# Invoke yt-dlp as a subprocess, not as a Python library

- Status: accepted
- Date: 2025-12-05 (reconstructed 2026-07-12 from the original `.kiro` design)

## Context

yt-dlp offers a Python API, but it is explicitly unstable across releases,
holds the GIL during extraction, and couples the app to yt-dlp internals.
YouTube breakage requires frequent yt-dlp updates that must not require app
code changes.

## Decision

Execute the `yt-dlp` binary via `asyncio.create_subprocess_exec` with
argument lists (never a shell), parse `--dump-json` output, and manage
retries/timeouts/cleanup around the process boundary.

## Consequences

- yt-dlp can be updated independently of the application (weekly image
  refresh, pinned via requirements-ytdlp.txt since v0.2.0)
- Command construction must be validated to prevent argument injection
  (URL validator, format regex, template sanitizer)
- Test mode swaps the executor with a mock instead of monkeypatching internals
