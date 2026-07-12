# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Browser TLS-fingerprint impersonation in the image: yt-dlp is now
  installed with the `default` and `curl-cffi` extras, removing the
  "no impersonate target is available" warning and improving resilience
  against anti-bot blocks, especially from datacenter IPs

## [0.2.1] - 2026-07-12

Fixes from the first production deployment against real YouTube (all three
issues were structurally masked by test mode).

### Fixed

- **Read-only cookie mounts work again**: yt-dlp rewrites the cookie jar on
  every run, so the documented `:ro` cookies mount crashed every real
  invocation with `OSError: Read-only file system`. Executions now run
  against a private writable copy of the cookie file, discarded afterwards;
  the hot-reload endpoint remains the cookie refresh path (jar rotation is
  no longer persisted)
- **PO-token subtitle failures**: the hardcoded
  `--extractor-args youtube:player_client=web` triggered YouTube's PO-token
  requirement and got web-client subtitles discarded. The forced client is
  removed in favor of yt-dlp's maintained client selection
- **Signature solving**: pip installs of yt-dlp do not bundle the EJS
  challenge-solver scripts; `yt-dlp-ejs` is now installed in the image,
  fixing `/info` degrading to images-only

## [0.2.0] - 2026-07-12

First release with the differentiator features: transcripts as data, signed webhooks, published multi-arch images.

### Added

- **Transcript endpoint**: `GET /api/v1/transcript` returns manual subtitles
  or auto-captions as timed JSON segments, plain text, SRT or raw VTT,
  without downloading media (`lang`, `source=any|manual|auto`, `fmt`
  parameters; 404 `TRANSCRIPT_NOT_FOUND` when no captions exist). The WebVTT
  parser deduplicates YouTube auto-caption rolling cues and strips inline
  word-level tags
- **Job completion webhooks**: optional `webhook_url` on download requests;
  HMAC-SHA256-signed `job.completed`/`job.failed` POSTs with retries and
  exponential backoff; disabled by default with an exact-host allowlist
  (SSRF protection); `webhook_deliveries_total` metric; new
  `APP_WEBHOOKS_*` configuration section
- **Published images**: multi-arch (linux/amd64, linux/arm64) builds pushed
  to `ghcr.io/fvadicamo/yt-dlp-api` on every release (semver + `latest`)
  and weekly as `weekly` with the latest yt-dlp; every image passes the
  container smoke test before push
- yt-dlp pinned in `requirements-ytdlp.txt` (dependabot-managed) instead of
  installed unpinned at build time
- Architecture Decision Records in `.s2s/decisions/` (0001-0007)
- Repo-level gitleaks config with anchored placeholder allowlist

### Changed

- README repositioned as reference documentation: image-first quick start,
  positioning section, integration recipes, mermaid architecture diagram
- pydantic 2.5.3 -> 2.13.4, pydantic-settings 2.1.0 -> 2.14.2 (removes the
  fastapi Field(deprecated=...) warning storm); httpx 0.28.1 promoted to
  runtime dependency (webhook delivery client)
- Test suite: 893 tests at 94% coverage with zero warnings; coverage gate
  raised from 80 to 90; weak modules covered to 100% (provider manager,
  download worker, download/video endpoints)

### Fixed

- Unreadable cookie file/volume now degrades the provider instead of
  crashing startup with an uncaught `PermissionError`, even in degraded
  mode (found by the container smoke test)

## [0.1.6] - 2026-07-11

Maintenance and security release: real CI quality gates, dependency modernization, repo hygiene.

### Added

- CI workflow with blocking quality gates on PRs and pushes to develop/main,
  dependabot included: lint (black, isort, flake8, mypy, bandit), tests with
  90% coverage floor, secret scan (gitleaks), Docker build + container smoke test
- Container smoke test script (`scripts/docker_smoke.sh`): boots the image in
  test mode and exercises liveness, docs, metrics, auth rejection and mocked
  video info from outside the container
- Secret scanning (gitleaks) and local privacy guard hooks in pre-commit
- Spec2Ship project tracking (`.s2s/`): live backlog, context and ideas;
  `.kiro/specs/` remains as the original MVP spec archive

### Changed

- Test stack modernized: pytest 7.4.4 -> 9.1.1, pytest-asyncio 0.23.3 -> 1.4.0,
  pytest-cov 4.1.0 -> 7.1.0, pytest-mock 3.12.0 -> 3.15.1
- Tooling: mypy 1.8.0 -> 1.19.1, flake8-simplify 0.21.0 -> 0.22.0
- Runtime: structlog 24.1.0 -> 25.5.0; fastapi, uvicorn and psutil now pinned
  to exact tested versions (0.125.0, 0.51.0, 7.2.2)
- GitHub Actions: actions/checkout v4/v5 -> v6, actions/upload-artifact v4 -> v6
- Branch protection required checks switched from advisory AI review jobs to
  the blocking CI jobs (unblocks dependabot PRs, which previously never
  received the required contexts)
- pyproject.toml metadata fixed (real repository URLs, author) and
  dependencies aligned with requirements.txt as the canonical source
- Dockerfile: stale hardcoded version label replaced with OCI annotations and
  a `VERSION` build argument

### Fixed

- Application version now reports the released version (was hardcoded 1.0.0
  in `/health` and OpenAPI since v0.1.0)
- Makefile: deprecated pre-commit `--hook-type push` corrected to `pre-push`

### Security

- **run-gemini-cli** 0.1.18 -> 0.1.22: critical RCE advisory (workspace trust
  and tool allowlisting bypasses)
- **black** 24.3.0 -> 26.5.1: arbitrary file write from unsanitized user input
  in cache file name (high)
- **pytest** 7.4.4 -> 9.1.1: vulnerable tmpdir handling (medium)

## [0.1.5] - 2025-12-26

Dependency updates and maintenance release.

### Changed

- **GitHub Actions**: Updated to latest versions
  - `actions/setup-python` v5 -> v6
  - `actions/github-script` v7 -> v8
  - `google-github-actions/run-gemini-cli` v0.1.14 -> v0.1.18
- **Python Dependencies**: Updated to latest versions
  - `prometheus-client` 0.19.0 -> 0.23.1
  - `cachetools` 5.3.2 -> 6.2.4
  - `pre-commit` 3.6.0 -> 4.5.1
  - `flake8-comprehensions` 3.14.0 -> 3.17.0
  - `pep8-naming` 0.13.3 -> 0.15.1
  - `types-cachetools` 5.3.0.7 -> 6.2.0.20251022
- **Dependabot**: Now targets `develop` branch instead of `main`
- **Labels**: Simplified to use only `dependencies` label for all Dependabot PRs
- **Pre-commit**: Fixed deprecated `stages: [push]` to `stages: [pre-push]`

### Fixed

- Flaky test `test_request_increments_counter` now uses specific Prometheus counter parsing instead of content length comparison (#43, #44)

## [0.1.3] - 2025-12-26

Security hardening and CI/CD improvements.

### Added

- Dependabot configuration for automated dependency updates
  - Python packages (pip): weekly updates, limit 5 PRs
  - GitHub Actions: weekly updates, limit 3 PRs
  - Docker images: weekly updates, limit 3 PRs

### Security

- **codex-review.yml**: Convert all GitHub context interpolations to environment variables to prevent shell injection (fixes CodeQL #2)
- **codex-review.yml**: Restrict `@codex review` command to OWNER/MEMBER/COLLABORATOR only (fixes CodeQL #1)
- **gemini-review.yml**: Add explicit `permissions: contents: read` to lint job (fixes CodeQL #3)

## [0.1.2] - 2025-12-26

Public release preparation with OSS files.

### Added

- MIT License (Copyright 2025 Francesco Vadicamo)
- SECURITY.md with GitHub Private Vulnerability Reporting policy
- CONTRIBUTING.md with development setup and guidelines
- GitHub Issue Templates (bug report, feature request)
- Pull Request Template with checklist

## [0.1.1] - 2025-12-26

Bug fixes from v0.1.0 release review.

### Fixed

- Job cleanup TTL now correctly based on `completed_at` instead of `created_at` (#20)
- `hash_api_key` function accepts `Optional[str]` with `sha256:` prefix format (#21)
- Docker build optimization: yt-dlp installed in builder stage (#22)

### Changed

- Updated related tests to match new behavior

## [0.1.0] - 2025-12-25

Initial MVP release of yt-dlp REST API.

### Added

#### Core Infrastructure
- FastAPI application with async request handling
- Configuration management with YAML file and environment variable support
- Structured JSON logging with request ID propagation and sensitive data redaction
- Pydantic-based configuration validation

#### Video Provider System
- Abstract provider interface for multi-platform support
- YouTube provider implementation with full yt-dlp integration
- Cookie-based authentication with hot-reload support
- Automatic retry logic with exponential backoff (2s, 4s, 8s)
- Transient error detection and recovery

#### Cookie Management
- Netscape format cookie file parsing and validation
- Cookie expiry detection with 7-day warning threshold
- Hot-reload endpoint for updating cookies without restart
- Provider-specific cookie path configuration

#### Security
- API key authentication middleware
- Multi-key support for team access
- URL validation against injection attacks
- Format ID validation to prevent command injection
- Template processor with path traversal prevention
- Sensitive data redaction in logs (API keys, cookies)

#### Rate Limiting
- Token bucket rate limiter implementation
- Separate limits for metadata (100 rpm) and download (10 rpm) operations
- Burst capacity support for traffic spikes
- Retry-After header in 429 responses

#### Storage Management
- Configurable download directory with automatic creation
- Age-based file cleanup scheduler
- Disk usage threshold monitoring
- Maximum file size enforcement

#### Job Management
- Async download queue with priority support
- Job status tracking (pending, processing, completed, failed)
- Progress reporting during downloads
- Configurable job TTL for automatic cleanup
- Concurrent download limit enforcement

#### API Endpoints
- `GET /health` - Component health status
- `GET /liveness` - Kubernetes liveness probe
- `GET /readiness` - Kubernetes readiness probe
- `GET /metrics` - Prometheus metrics endpoint
- `GET /api/v1/info` - Video metadata extraction
- `GET /api/v1/formats` - Available format listing
- `POST /api/v1/download` - Async download job creation
- `GET /api/v1/jobs/{id}` - Job status retrieval
- `POST /api/v1/admin/validate-cookie` - Cookie validation
- `POST /api/v1/admin/reload-cookie` - Cookie hot-reload

#### Monitoring
- Prometheus metrics collection
- Request count, latency, and error rate metrics
- Download queue depth and job status metrics
- YouTube connectivity health check
- Structured logging with correlation IDs

#### Startup Validation
- Component initialization checks
- Cookie file validation on startup
- Degraded mode support for development
- Clear error reporting for missing dependencies

#### Docker Support
- Multi-stage Dockerfile with Python 3.11-slim
- Non-root container execution (UID 1000)
- Pre-installed ffmpeg and Node.js 20+
- Docker Compose configuration with resource limits
- Health check configuration
- Volume mounts for downloads, cookies, and logs

#### Testing Infrastructure
- Test mode configuration for development without YouTube access
- Mock yt-dlp executor with demo video data
- End-to-end test suite covering complete API workflow
- Resource monitoring and validation utilities

#### Documentation
- Comprehensive README with quick start guide
- API usage examples with curl
- Cookie export instructions for Chrome and Firefox
- Deployment guide for Docker and Kubernetes
- Complete configuration reference with 30+ environment variables
- Error codes and troubleshooting guide
- Resource requirements documentation (minimum, recommended, high-load tiers)

### Changed

- Admin endpoints now use JSON request body instead of query parameters (REST best practice)

### Security

- Container runs as non-root user by default
- API key authentication required for all API endpoints
- Input validation prevents command injection
- Path traversal protection in template processor
- Sensitive data redaction in all log output
- Trivy security scan passed (0 critical vulnerabilities)
- Fixed CVE-2024-47874 (DoS vulnerability in starlette) by upgrading FastAPI to 0.115.6

[Unreleased]: https://github.com/fvadicamo/yt-dlp-api/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/fvadicamo/yt-dlp-api/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/fvadicamo/yt-dlp-api/compare/v0.1.6...v0.2.0
[0.1.6]: https://github.com/fvadicamo/yt-dlp-api/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/fvadicamo/yt-dlp-api/compare/v0.1.3...v0.1.5
[0.1.3]: https://github.com/fvadicamo/yt-dlp-api/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/fvadicamo/yt-dlp-api/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/fvadicamo/yt-dlp-api/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/fvadicamo/yt-dlp-api/releases/tag/v0.1.0
