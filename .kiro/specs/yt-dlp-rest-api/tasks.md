# Implementation Plan

## Overview

This implementation plan breaks down the yt-dlp REST API Backend into incremental, testable tasks. Each task builds on previous work and references specific requirements from the requirements document.

## MVP Scope

For rapid and robust delivery, the following are REQUIRED:

**Core Implementation**
- All tasks 1-13 (setup through Docker containerization)

**Critical Testing (Required for MVP)**
- Task 1.4: Configuration and logging tests
- Task 3.4: Cookie management tests (CRITICAL - operational pain point)
- Task 4.7: YouTube provider tests (CRITICAL - core value stream)
- Task 5.4: Security tests (path traversal, input validation, log redaction)
- Task 11.4: Startup validation tests (degraded mode)
- Task 15.3: Basic security validation (no secrets, common exploits)

**Documentation**
- Task 14.1: README.md
- Task 14.2: DEPLOYMENT.md

**Optional for MVP** (manual validation or post-MVP)
- Advanced tests: rate limiter, storage policies, job lifecycle, monitoring, API integration, E2E
- Task 14.3: CONFIGURATION.md (can be covered in README initially)
- Task 14.4: CHANGELOG.md (can be added later)
- Task 15.2: End-to-end tests (manual validation sufficient for MVP)
- Task 13.4: Docker deployment tests (manual validation sufficient)

**Rationale**: Cookie management, YouTube provider, and security have been the primary sources of errors, downtime, and debug time in production. These must be tested automatically. Other system components can be validated manually or in subsequent sprints without blocking a useful and operable MVP.

---

- [ ] 1. Project Setup and Core Infrastructure
  - Initialize Python project with FastAPI, create directory structure, configure development environment
  - _Requirements: 19, 20, 40, 41_

- [ ] 1.1 Initialize project structure and dependencies
  - Create project directory layout (app/, tests/, docker/, docs/)
  - Create requirements.txt with FastAPI, uvicorn, pydantic, structlog, prometheus-client, pyyaml, cachetools
  - Create requirements-dev.txt with pytest, pytest-asyncio, pytest-mock, pytest-cov, httpx
  - Create pyproject.toml with project metadata
  - _Requirements: 40_

- [ ] 1.2 Set up configuration management
  - Implement ConfigService class to load YAML configuration
  - Add environment variable override logic with APP_ prefix
  - Create default config.yaml with all configuration sections
  - Add configuration validation logic
  - _Requirements: 19, 20_

- [ ] 1.3 Set up structured logging
  - Configure structlog for JSON output
  - Implement request_id context variable and propagation
  - Create log level configuration (DEBUG, INFO, WARNING, ERROR)
  - Add API key hashing utility for safe logging
  - _Requirements: 17, 17A, 33_

- [ ] 1.4 Write configuration and logging tests
  - Test YAML loading and parsing
  - Test environment variable overrides
  - Test configuration validation
  - Test log redaction effectiveness
  - _Requirements: 17A_

---

- [ ] 2. Provider Abstraction Layer
  - Define provider interface, implement provider manager, create YouTube provider skeleton
  - _Requirements: 34, 35_

- [ ] 2.1 Define provider interface and data models
  - Create VideoProvider abstract base class with validate_url, get_info, list_formats, download methods
  - Define VideoInfo, VideoFormat, Subtitle, DownloadResult dataclasses
  - Create provider exceptions hierarchy
  - _Requirements: 34_

- [ ] 2.2 Implement provider manager
  - Create ProviderManager class for provider registration and selection
  - Implement URL-based provider selection logic
  - Add provider lifecycle management (enable/disable)
  - Add error isolation for provider failures
  - _Requirements: 34_

- [ ] 2.3 Create YouTube provider skeleton
  - Implement YouTubeProvider class extending VideoProvider
  - Add URL validation with regex patterns for watch, shorts, embed, mobile URLs
  - Implement video ID extraction logic
  - Add provider configuration loading
  - _Requirements: 35_

- [ ]* 2.4 Write provider abstraction tests
  - Test provider registration and selection
  - Test URL validation for various YouTube formats
  - Test provider error isolation
  - _Requirements: 34, 35_

---

- [ ] 3. Cookie Management System
  - Implement cookie service with validation, caching, and hot-reload
  - _Requirements: 8, 8A, 8B, 23, 23A_

- [ ] 3.1 Implement cookie service
  - Create CookieService class with file loading and validation
  - Add Netscape format validation
  - Implement per-provider cookie path configuration
  - Add cookie file age checking with 7-day warning
  - _Requirements: 8, 23, 23A_

- [ ] 3.2 Add cookie validation caching
  - Implement TTL cache for validation results (1 hour)
  - Add file modification time tracking for cache invalidation
  - Create validate_cookie method with YouTube test
  - Add cache invalidation within 60 seconds of file modification
  - _Requirements: 8A_

- [ ] 3.3 Implement cookie hot-reload endpoint
  - Create POST /api/v1/admin/reload-cookie endpoint
  - Add cookie validation before applying reload
  - Implement rollback to previous cookie on validation failure
  - Add reload operation logging
  - _Requirements: 8B_

- [ ] 3.4 Write cookie management tests (CRITICAL)
  - Test cookie file loading and validation
  - Test cache behavior and invalidation
  - Test hot-reload success and failure scenarios
  - Test authentication with real YouTube test
  - _Requirements: 8, 8A, 8B_

---

- [ ] 4. YouTube Provider Implementation
  - Implement metadata extraction, format listing, and download functionality
  - _Requirements: 1, 2, 3, 4, 5, 6, 35_

- [ ] 4.1 Implement metadata extraction
  - Create get_info method using yt-dlp --dump-json
  - Parse JSON output to VideoInfo format
  - Add optional format and subtitle inclusion
  - Implement 10-second timeout
  - Add cookie validation before execution
  - _Requirements: 1, 35_

- [ ] 4.2 Implement format listing
  - Create list_formats method to extract available formats
  - Parse format information (ID, extension, resolution, codecs, filesize)
  - Categorize formats as video+audio, video-only, audio-only
  - Sort formats by quality (highest to lowest)
  - _Requirements: 2, 35_

- [ ] 4.3 Implement subtitle discovery
  - Add subtitle parsing from yt-dlp output
  - Extract language, format (VTT/SRT), and auto-generated flag
  - Integrate with get_info method
  - _Requirements: 3, 35_

- [ ] 4.4 Implement video download
  - Create download method with format selection
  - Add output template processing
  - Implement subtitle download with language selection
  - Add file path extraction from yt-dlp output
  - Log command execution with redaction (Req 17A)
  - Log stdout, stderr, and exit code after execution
  - _Requirements: 4, 6, 17A, 35_

- [ ] 4.5 Implement audio extraction
  - Add audio-only download with format conversion
  - Support MP3, M4A, WAV, OPUS formats
  - Implement quality selection (128kbps, 192kbps, 320kbps)
  - Add video track removal logic
  - _Requirements: 5, 35_

- [ ] 4.6 Add retry logic with exponential backoff
  - Implement _execute_with_retry method
  - Add retriable error detection (network timeout, HTTP 5xx)
  - Configure 3 retry attempts with 2, 4, 8 second backoff
  - Log each retry attempt
  - _Requirements: 18, 35_

- [ ] 4.7 Write YouTube provider tests (CRITICAL)
  - Test metadata extraction with mock yt-dlp output
  - Test format parsing and categorization
  - Test download with various parameters
  - Test retry logic for transient errors
  - Test error classification (retriable vs non-retriable)
  - _Requirements: 1, 2, 4, 5, 18, 35_

---

- [ ] 5. Input Validation and Security
  - Implement URL validation, template sanitization, and API key authentication
  - _Requirements: 7, 9, 31, 33_

- [ ] 5.1 Implement input validation utilities
  - Create URL validator with domain whitelist (youtube.com, youtu.be)
  - Implement format ID regex validation
  - Add parameter type and range validation
  - _Requirements: 31_

- [ ] 5.2 Implement template processor
  - Create TemplateProcessor class for output templates
  - Add path traversal prevention
  - Implement filesystem character sanitization
  - Add template variable validation
  - Implement filename collision handling with numeric suffix
  - _Requirements: 7, 31_

- [ ] 5.3 Implement API key authentication
  - Create auth middleware for API key validation
  - Add API key extraction from X-API-Key header
  - Implement multi-key support
  - Add unauthorized access logging
  - Exclude /health, /docs endpoints from authentication
  - _Requirements: 9, 33_

- [ ] 5.4 Write security tests (CRITICAL)
  - Test path traversal prevention
  - Test URL validation with malicious inputs
  - Test API key authentication and rejection
  - Test sensitive data redaction in logs
  - Test template sanitization edge cases
  - _Requirements: 7, 9, 31, 33_

---

- [ ] 6. Rate Limiting System
  - Implement token bucket rate limiter with per-API-key limits
  - _Requirements: 27_

- [ ] 6.1 Implement token bucket rate limiter
  - Create TokenBucket dataclass with capacity, refill_rate, tokens
  - Implement RateLimiter class with per-API-key, per-category buckets
  - Add token refill logic based on elapsed time
  - Configure separate limits for metadata (100 rpm) and download (10 rpm) operations
  - Add burst capacity support (20 tokens)
  - _Requirements: 27_

- [ ] 6.2 Create rate limiting middleware
  - Implement rate_limit_middleware for FastAPI
  - Add endpoint category detection (metadata vs download)
  - Return HTTP 429 with Retry-After header when limit exceeded
  - Log rate limiting events with API key hash
  - _Requirements: 27_

- [ ]* 6.3 Write rate limiter tests
  - Test token bucket refill logic
  - Test rate limit enforcement per category
  - Test burst allowance behavior
  - Test Retry-After header calculation
  - _Requirements: 27_

---

- [ ] 7. Storage and File Management
  - Implement storage manager with cleanup, disk monitoring, and file size limits
  - _Requirements: 22, 24, 25_

- [ ] 7.1 Implement storage manager
  - Create StorageManager class with output directory management
  - Add disk usage monitoring
  - Implement file size validation before download
  - Add active job tracking by job_id
  - Create directory at startup if not exists
  - _Requirements: 22, 25_

- [ ] 7.2 Implement automatic cleanup
  - Add cleanup_old_files method with age-based deletion
  - Implement disk usage threshold check (80% default)
  - Add active job file preservation
  - Implement dry-run mode for cleanup testing
  - Log deleted files with size and age
  - _Requirements: 24_

- [ ] 7.3 Create cleanup scheduler
  - Implement periodic cleanup task (hourly)
  - Add cleanup trigger based on disk usage threshold
  - Log cleanup results (files deleted, space reclaimed)
  - _Requirements: 24_

- [ ]* 7.4 Write storage management tests
  - Test disk usage calculation
  - Test file size validation
  - Test cleanup with age and threshold conditions
  - Test active job file preservation
  - _Requirements: 22, 24, 25_

---

- [ ] 8. Job Management System
  - Implement asynchronous job tracking with status updates
  - _Requirements: 14, 15, 26_

- [ ] 8.1 Implement job data model
  - Create JobStatus enum (PENDING, PROCESSING, RETRYING, COMPLETED, FAILED)
  - Define Job dataclass with job_id, status, progress, retry_count, timestamps
  - Add job result fields (file_path, file_size, duration)
  - _Requirements: 15_

- [ ] 8.2 Implement job service
  - Create JobService class with in-memory job storage
  - Add job creation with UUID generation
  - Implement job status updates and progress tracking
  - Add 24-hour TTL for job history
  - _Requirements: 15_

- [ ] 8.3 Implement download queue
  - Create priority queue with metadata operations prioritized
  - Add concurrent download limiting (5 default)
  - Implement queue position tracking
  - Add automatic queue processing when downloads complete
  - _Requirements: 26_

- [ ] 8.4 Implement download worker
  - Create async download worker that processes queued jobs
  - Add job status transitions (PENDING → PROCESSING → COMPLETED/FAILED)
  - Implement retry logic with RETRYING state
  - Add progress tracking during download
  - Register/unregister files with storage manager
  - _Requirements: 14, 15, 26_

- [ ]* 8.5 Write job management tests
  - Test job creation and status updates
  - Test queue priority and concurrency limits
  - Test job TTL and cleanup
  - Test retry state transitions
  - _Requirements: 14, 15, 26_

---

- [ ] 9. API Endpoints Implementation
  - Create FastAPI endpoints for video operations, jobs, and admin functions
  - _Requirements: 11, 12, 13, 14, 15, 8B_

- [ ] 9.1 Implement health check endpoints
  - Create GET /health endpoint with component verification
  - Add GET /liveness endpoint for container orchestration
  - Create GET /readiness endpoint for load balancer integration
  - Verify yt-dlp, ffmpeg, Node.js, cookies, storage in health checks
  - Return HTTP 200 for healthy, HTTP 503 for unhealthy
  - _Requirements: 11, 37_

- [ ] 9.2 Implement video info endpoint
  - Create GET /api/v1/info endpoint
  - Add query parameters: url, include_formats, include_subtitles
  - Implement request validation
  - Call provider manager to get video information
  - Return VideoInfo response with optional formats and subtitles
  - _Requirements: 12_

- [ ] 9.3 Implement formats endpoint
  - Create GET /api/v1/formats endpoint
  - Add url query parameter
  - Call provider to list formats
  - Return formats grouped by type and sorted by quality
  - _Requirements: 13_

- [ ] 9.4 Implement download endpoint
  - Create POST /api/v1/download endpoint
  - Add request body with url, format_id, output_template, extract_audio, audio_format, include_subtitles, subtitle_lang, async
  - Validate all parameters
  - Create job and enqueue download
  - Support synchronous (wait) and asynchronous (return job_id) modes
  - _Requirements: 14_

- [ ] 9.5 Implement job status endpoint
  - Create GET /api/v1/jobs/{job_id} endpoint
  - Return job status, progress, file_path, error_message
  - Return HTTP 404 if job not found
  - _Requirements: 15_

- [ ] 9.6 Implement admin endpoints
  - Create POST /api/v1/admin/validate-cookie endpoint
  - Create POST /api/v1/admin/reload-cookie endpoint
  - Add authentication requirement for admin endpoints
  - _Requirements: 8A, 8B_

- [ ]* 9.7 Write API endpoint tests
  - Test all endpoints with valid and invalid inputs
  - Test authentication enforcement
  - Test error responses and status codes
  - Test async and sync download modes
  - _Requirements: 11, 12, 13, 14, 15_

---

- [ ] 10. Error Handling and Monitoring
  - Implement standardized error responses, metrics collection, and Prometheus export
  - _Requirements: 16, 29, 30_

- [ ] 10.1 Implement error handling
  - Define error code constants (INVALID_URL, VIDEO_UNAVAILABLE, etc.)
  - Create error response model with code, message, details, timestamp, suggestion
  - Implement error code to HTTP status mapping
  - Add global exception handler for FastAPI
  - _Requirements: 16_

- [ ] 10.2 Implement metrics collection
  - Create Prometheus metrics (http_requests_total, download_duration_seconds, etc.)
  - Add metrics for requests, downloads, queue, storage, rate limiting, cookies, errors by type
  - Implement metrics update in middleware and services
  - Create GET /metrics endpoint for Prometheus scraping
  - _Requirements: 29_

- [ ] 10.3 Enhance health check with detailed status
  - Add component version detection (yt-dlp, ffmpeg, Node.js)
  - Add cookie age and status per provider
  - Add disk space monitoring
  - Add YouTube connectivity test
  - Calculate and include system uptime
  - _Requirements: 30_

- [ ]* 10.4 Write monitoring tests
  - Test error response format and codes
  - Test metrics collection and export
  - Test health check component verification
  - _Requirements: 16, 29, 30_

---

- [ ] 11. Startup Validation and Initialization
  - Implement startup checks for dependencies and configuration
  - _Requirements: 10, 21, 22, 23, 47_

- [ ] 11.1 Implement startup validator
  - Create StartupValidator class with component checks
  - Add yt-dlp version check
  - Add ffmpeg availability check
  - Add Node.js >= 20 version check
  - Add cookie file validation with authentication test
  - Add storage directory and permissions check
  - _Requirements: 10, 21, 22, 23_

- [ ] 11.2 Implement degraded mode support
  - Add ALLOW_DEGRADED_START configuration option
  - Allow startup with warnings when degraded mode enabled
  - Disable providers with missing cookies in degraded mode
  - Return HTTP 503 for endpoints requiring unavailable components
  - Log degraded mode status at startup
  - _Requirements: 47_

- [ ] 11.3 Configure yt-dlp for Node.js runtime
  - Set --js-runtimes node flag in yt-dlp configuration
  - Create yt-dlp config file if not exists
  - Verify Node.js runtime configuration
  - _Requirements: 10, 21_

- [ ] 11.4 Write startup validation tests
  - Test component availability checks
  - Test degraded mode behavior
  - Test startup failure scenarios
  - Test cookie validation at startup
  - _Requirements: 10, 21, 47_

---

- [ ] 12. FastAPI Application Assembly
  - Wire all components together and create main application entry point
  - _Requirements: 19, 20, 39, 46_

- [ ] 12.1 Create FastAPI application
  - Initialize FastAPI app with metadata
  - Configure CORS if needed
  - Add middleware (auth, rate limiting, request ID, logging)
  - Register API routers for v1 endpoints
  - Add exception handlers
  - _Requirements: 46_

- [ ] 12.2 Implement dependency injection
  - Create FastAPI dependencies for config, providers, services
  - Add lifespan context manager for startup/shutdown
  - Initialize all services on startup
  - Run startup validation
  - Start background tasks (cleanup scheduler)
  - _Requirements: 19, 20_

- [ ] 12.3 Configure OpenAPI documentation
  - Add API metadata (title, version, description)
  - Configure Swagger UI at /docs
  - Add request/response examples to endpoints
  - Document all error codes
  - _Requirements: 39_

- [ ]* 12.4 Write integration tests
  - Test full request flow from client to response
  - Test middleware chain execution
  - Test dependency injection
  - Test startup and shutdown lifecycle
  - _Requirements: 39, 46_

---

- [ ] 13. Docker Containerization
  - Create Dockerfile and docker-compose configuration
  - _Requirements: 32, 41, 42, 43_

- [ ] 13.1 Create multi-stage Dockerfile
  - Create builder stage with Python dependencies
  - Create runtime stage with Python 3.11-slim
  - Install system dependencies (ffmpeg, nodejs >= 20)
  - Create non-root user (appuser, UID 1000)
  - Copy application code with correct ownership
  - Create output, cookie, log directories
  - Configure read-only filesystem with writable volumes
  - Add health check configuration
  - _Requirements: 32, 41_

- [ ] 13.2 Create docker-compose.yml
  - Define ytdlp-api service
  - Configure port mappings (8000, 9090)
  - Add environment variables
  - Mount volumes for downloads, cookies, config, logs
  - Add health check configuration
  - Set resource limits (CPU, memory)
  - Configure restart policy
  - _Requirements: 42_

- [ ] 13.3 Create .dockerignore
  - Exclude tests, docs, .git, __pycache__, *.pyc
  - Exclude development files
  - _Requirements: 41_

- [ ]* 13.4 Test Docker deployment
  - Build Docker image
  - Run container with docker-compose
  - Verify health check passes
  - Test API endpoints from host
  - Verify volume mounts work correctly
  - _Requirements: 41, 42, 43_

---

- [ ] 14. Documentation
  - Create comprehensive documentation for deployment and usage
  - _Requirements: 40_

- [ ] 14.1 Create README.md
  - Add project overview and features
  - Add quick start guide
  - Document system requirements
  - Add cookie export instructions for Chrome and Firefox
  - Provide curl examples for all endpoints
  - Add troubleshooting section
  - _Requirements: 40_

- [ ] 14.2 Create DEPLOYMENT.md
  - Document Docker deployment steps
  - Add Kubernetes deployment example
  - Document environment variable configuration
  - Add production deployment best practices
  - _Requirements: 40_

- [ ] 14.3 Create CONFIGURATION.md
  - Document all configuration options in config.yaml
  - Document all environment variables
  - Provide configuration examples for common scenarios
  - Document provider configuration
  - _Requirements: 40_

- [ ] 14.4 Create CHANGELOG.md
  - Document initial version features
  - Set up changelog format for future updates
  - _Requirements: 44_

---

- [ ] 15. Final Integration and Testing
  - Perform end-to-end testing and validation
  - _Requirements: 38_

- [ ] 15.1 Create test mode configuration
  - Add TEST_MODE environment variable
  - Create demo video fixtures
  - Implement yt-dlp command mocking for tests
  - Add test mode indicator in logs and health checks
  - _Requirements: 38_

- [ ]* 15.2 Run end-to-end tests
  - Test complete download workflow
  - Test error scenarios and recovery
  - Test rate limiting under load
  - Test cookie hot-reload
  - Test cleanup scheduler
  - Verify metrics collection
  - _Requirements: 38_

- [ ] 15.3 Perform basic security validation
  - Run security scanner on Docker image (Trivy or Snyk)
  - Verify no secrets in image layers
  - Test common input validation exploits
  - Verify log redaction with automated checks
  - _Requirements: 32, 33_

- [ ] 15.4 Validate resource requirements
  - Test with minimum resources (1GB RAM, 2 CPU)
  - Measure actual resource usage under load
  - Document recommended resources for production
  - _Requirements: 43_
