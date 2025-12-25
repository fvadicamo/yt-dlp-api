# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

#### Documentation
- Comprehensive README with quick start guide
- API usage examples with curl
- Cookie export instructions for Chrome and Firefox
- Deployment guide for Docker and Kubernetes
- Complete configuration reference
- Error codes and troubleshooting guide

### Security

- Container runs as non-root user by default
- API key authentication required for all API endpoints
- Input validation prevents command injection
- Path traversal protection in template processor
- Sensitive data redaction in all log output
- Trivy security scan passed (0 critical vulnerabilities)

[Unreleased]: https://github.com/fvadicamo/yt-dlp-api/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/fvadicamo/yt-dlp-api/releases/tag/v0.1.0
