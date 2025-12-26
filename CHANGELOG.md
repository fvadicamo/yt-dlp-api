# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/fvadicamo/yt-dlp-api/compare/v0.1.5...HEAD
[0.1.5]: https://github.com/fvadicamo/yt-dlp-api/compare/v0.1.3...v0.1.5
[0.1.3]: https://github.com/fvadicamo/yt-dlp-api/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/fvadicamo/yt-dlp-api/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/fvadicamo/yt-dlp-api/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/fvadicamo/yt-dlp-api/releases/tag/v0.1.0
