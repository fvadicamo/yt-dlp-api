# Blocking CI gates and GHCR distribution with weekly yt-dlp refresh

- Status: accepted
- Date: 2026-07-11

## Context

Until v0.1.6 the only PR checks were advisory AI reviews
(continue-on-error) that skipped dependabot, leaving 9 dependabot PRs
unmergeable and no image published anywhere (users had to clone and build).
yt-dlp was installed unpinned at build time, invisible to dependabot,
while YouTube changes regularly break old yt-dlp versions (requirement 45).

## Decision

Dedicated `ci.yml` with four required contexts (Lint, Tests with coverage
>= 90, Secret Scan, Docker Smoke) on all PRs including dependabot;
`docker-publish.yml` builds multi-arch images on release tags (semver +
latest) and a weekly `weekly` tag with the latest yt-dlp; yt-dlp pinned in
`requirements-ytdlp.txt` so dependabot bumps it.

## Consequences

- Branch protection is enforced by real gates; AI reviews stay advisory
- Releases are reproducible; freshness is available via `weekly`
- Every published image passes the container smoke test first
