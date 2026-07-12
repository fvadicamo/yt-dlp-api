# Provider abstraction with per-provider cookies

- Status: accepted
- Date: 2025-12-05 (reconstructed 2026-07-12 from the original `.kiro` design)

## Context

The MVP targets YouTube, but yt-dlp supports hundreds of sites and future
providers must not require core changes. Each platform has its own
authentication (cookie) lifecycle.

## Decision

`VideoProvider` ABC (validate_url, get_info, list_formats, download,
get_transcript since v0.2.0) + `ProviderManager` doing URL-based selection
with error isolation. Cookies are configured per provider and validated by a
dedicated `CookieService` with TTL-cached checks and hot reload.

## Consequences

- New providers are additive (register in main.py; dynamic plugin loading
  from requirement 36 stays parked as IDEA-006)
- One provider's validation failure cannot break the others' selection
- The transcript capability defaults to "unsupported" so providers opt in
