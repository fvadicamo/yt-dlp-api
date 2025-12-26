# yt-dlp REST API Backend - Code Style Guide

## Project Context

This is a **containerized Python REST API** that provides programmatic access to YouTube video downloads and metadata extraction using yt-dlp as the core engine.

### Architecture Overview
- **Type**: Self-hosted microservice deployed on Ubuntu VPS
- **Language**: Python 3.11+
- **Framework**: FastAPI (async)
- **Containerization**: Docker with multi-stage builds
- **Deployment**: docker compose (v2)
- **Development**: GitFlow with feature branches → develop → main

### Core Components
- **Provider Abstraction Layer**: Pluggable video platform support (YouTube primary)
- **Rate Limiting**: Token bucket algorithm with Redis backend
- **Security**: API key authentication, input validation, non-root containers
- **Observability**: Structured JSON logging (structlog), Prometheus metrics
- **Testing**: pytest with async support, minimum 80% coverage

---

## Python Code Standards

### Style & Formatting
- **PEP 8 compliant** - strictly enforce
- **Line length**: 88 characters (Black formatter compatible)
- **Type hints**: Required for all function signatures, class attributes, and return types
- **Import order**: Standard library → Third-party → Local (use `isort`)
- **String quotes**: Double quotes `"` preferred, single `'` acceptable if consistent

### Async Best Practices
```python
# ✅ GOOD: Proper async/await usage
async def download_video(url: str) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return await process_response(response)

# ❌ BAD: Mixing sync/async incorrectly
def download_video(url: str) -> dict[str, Any]:
    response = requests.get(url)  # Blocks event loop!
    return process_response(response)
```

### Documentation (Google-style docstrings)
- **Required for**:
  - All public API endpoints (FastAPI routes)
  - Provider classes and their public methods
  - Utility functions in `app/utils/`
  - Configuration loaders

- **Optional but encouraged for**:
  - Private helper functions
  - Data models (Pydantic models have field descriptions)

- **NOT required for**:
  - Test functions (test name is the documentation)
  - Simple property getters/setters

```python
async def extract_metadata(
    url: str,
    provider: BaseProvider,
    options: Optional[dict[str, Any]] = None
) -> VideoMetadata:
    """Extract video metadata using the specified provider.

    Args:
        url: Valid video URL (must pass provider validation)
        provider: Provider instance (YouTubeProvider, etc.)
        options: Additional yt-dlp options to pass

    Returns:
        VideoMetadata object with title, duration, formats, etc.

    Raises:
        ValidationError: If URL is invalid for provider
        ProviderError: If metadata extraction fails
        RateLimitError: If rate limit is exceeded

    Example:
        >>> metadata = await extract_metadata(
        ...     "https://youtube.com/watch?v=dQw4w9WgXcQ",
        ...     youtube_provider
        ... )
        >>> print(metadata.title)
    """
```

---

## FastAPI & API Design

### Endpoint Structure
- **Versioning**: All routes under `/api/v1/`
- **HTTP Methods**:
  - `GET` for retrieval (metadata, status)
  - `POST` for actions (download, format extraction)
  - `DELETE` for cleanup (clear cache, cancel download)
- **Response Format**: Always JSON with consistent structure
- **Status Codes**: Use semantic HTTP codes (200, 201, 400, 401, 404, 429, 500, 503)

### Request/Response Models
```python
# ✅ GOOD: Pydantic models with validation
class DownloadRequest(BaseModel):
    url: HttpUrl  # Built-in validation
    format: str = Field(default="best", pattern="^(best|worst|[0-9]+p)$")
    extract_audio: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
                "format": "1080p",
                "extract_audio": False
            }
        }

@app.post("/api/v1/download", response_model=DownloadResponse, status_code=202)
async def download_video(
    request: DownloadRequest,
    api_key: str = Depends(verify_api_key),
    rate_limiter: RateLimiter = Depends(get_rate_limiter)
) -> DownloadResponse:
    """Download video with specified format."""
```

### Error Handling
```python
# ✅ GOOD: Structured error responses
class ErrorResponse(BaseModel):
    error: str
    detail: str
    timestamp: datetime
    request_id: str

@app.exception_handler(RateLimitError)
async def rate_limit_handler(request: Request, exc: RateLimitError):
    logger.warning(
        "rate_limit_exceeded",
        client_ip=request.client.host,
        limit=exc.limit,
        retry_after=exc.retry_after
    )
    return JSONResponse(
        status_code=429,
        content=ErrorResponse(
            error="Rate limit exceeded",
            detail=f"Retry after {exc.retry_after} seconds",
            timestamp=datetime.utcnow(),
            request_id=request.state.request_id
        ).model_dump(),
        headers={"Retry-After": str(exc.retry_after)}
    )
```

---

## Security Requirements

### Critical Security Checks (Zero Tolerance)

#### 1. Path Traversal Prevention
```python
# ✅ GOOD: Validate and sanitize paths
def get_download_path(filename: str) -> Path:
    base_dir = Path("/app/downloads").resolve()
    target = (base_dir / filename).resolve()

    if not target.is_relative_to(base_dir):
        raise SecurityError("Path traversal attempt detected")

    return target

# ❌ BAD: Direct path concatenation
def get_download_path(filename: str) -> Path:
    return Path(f"/app/downloads/{filename}")  # Vulnerable!
```

#### 2. Command Injection Prevention
```python
# ✅ GOOD: Use yt-dlp Python API, never shell commands
ydl_opts = {
    'format': validated_format,  # From enum/whitelist
    'outtmpl': str(safe_output_path)  # Pre-validated path
}
with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info(validated_url, download=True)

# ❌ BAD: Shell command with user input
import subprocess
subprocess.run(f"yt-dlp {user_url}", shell=True)  # NEVER DO THIS!
```

#### 3. Secrets Management
```python
# ✅ GOOD: Environment variables, never hardcoded
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    api_key: SecretStr
    redis_password: SecretStr

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# ❌ BAD: Hardcoded secrets
API_KEY = "sk-1234567890abcdef"  # NEVER COMMIT THIS!

# ❌ BAD: Secrets in logs
logger.info(f"Connecting with password: {password}")  # Exposes secret!

# ✅ GOOD: Redact secrets in logs
logger.info(f"Connecting with password: {'*' * 8}")
```

#### 4. Input Validation
```python
# ✅ GOOD: Whitelist validation
ALLOWED_FORMATS = {"best", "worst", "1080p", "720p", "480p", "360p"}

def validate_format(format_str: str) -> str:
    if format_str not in ALLOWED_FORMATS:
        raise ValidationError(f"Invalid format. Allowed: {ALLOWED_FORMATS}")
    return format_str

# ✅ GOOD: URL validation with provider-specific checks
async def validate_url(url: str, provider: BaseProvider) -> str:
    if not await provider.validate_url(url):
        raise ValidationError(f"Invalid URL for provider {provider.name}")
    return url
```

#### 5. Cookie File Security
```python
# ✅ GOOD: Secure cookie handling
def load_cookies(cookie_file: Path) -> dict[str, str]:
    # Verify file is within allowed directory
    if not cookie_file.is_relative_to(COOKIE_DIR):
        raise SecurityError("Cookie file outside allowed directory")

    # Set restrictive permissions (owner read-only)
    cookie_file.chmod(0o600)

    # Never log cookie contents
    logger.info(f"Loading cookies from {cookie_file.name}")  # Only filename

    return parse_cookie_file(cookie_file)
```

#### 6. Rate Limiting & DoS Protection
```python
# ✅ GOOD: Per-client rate limits with token bucket
@app.post("/api/v1/download")
async def download_video(
    request: DownloadRequest,
    rate_limiter: RateLimiter = Depends(get_rate_limiter)
):
    # Enforced by dependency injection
    await rate_limiter.check_limit(request.client.host)

    # Timeout on long operations
    async with asyncio.timeout(300):  # 5 min max
        result = await perform_download(request.url)

    return result
```

---

## Docker Best Practices

### Dockerfile Requirements
```dockerfile
# ✅ GOOD: Multi-stage build with security
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim
# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash appuser && \
    mkdir -p /app/downloads /app/logs && \
    chown -R appuser:appuser /app

WORKDIR /app
COPY --from=builder /root/.local /home/appuser/.local
COPY --chown=appuser:appuser . .

# Drop privileges
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml Best Practices
```yaml
services:
  api:
    build: .
    restart: unless-stopped
    environment:
      - REDIS_HOST=redis
      - REDIS_PASSWORD=${REDIS_PASSWORD}  # From .env
    volumes:
      - downloads:/app/downloads:rw
      - ./app:/app/app:ro  # Source code read-only
    networks:
      - backend
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
    # Security: drop capabilities, read-only root
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
    read_only: true
    tmpfs:
      - /tmp

volumes:
  downloads:
    driver: local
    driver_opts:
      type: none
      device: /var/app/downloads
      o: bind

networks:
  backend:
    driver: bridge
    internal: false  # Allow external access for API
```

---

## Testing Standards

### Coverage Requirements
- **Minimum overall coverage**: 80%
- **Critical paths**: 95%+ (authentication, download logic, provider abstraction)
- **Test types**: Both unit and integration tests required

### Test Structure
```python
# ✅ GOOD: Clear test structure with fixtures
import pytest
from httpx import AsyncClient

@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def mock_youtube_provider(mocker):
    provider = mocker.Mock(spec=YouTubeProvider)
    provider.validate_url.return_value = True
    provider.extract_info.return_value = {...}
    return provider

@pytest.mark.asyncio
async def test_download_endpoint_success(client, mock_youtube_provider):
    """Test successful video download request."""
    response = await client.post(
        "/api/v1/download",
        json={"url": "https://youtube.com/watch?v=test", "format": "best"},
        headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 202
    assert "task_id" in response.json()

@pytest.mark.asyncio
async def test_download_rate_limit_exceeded(client):
    """Test rate limiting enforcement on download endpoint."""
    # Make requests up to limit
    for _ in range(10):
        await client.post("/api/v1/download", ...)

    # Next request should be rate limited
    response = await client.post("/api/v1/download", ...)
    assert response.status_code == 429
    assert "Retry-After" in response.headers
```

### Test Organization
- `tests/unit/` - Fast, isolated tests (providers, utils, models)
- `tests/integration/` - API endpoint tests, database interactions
- `tests/security/` - Security-focused tests (injection, traversal, auth)
- `tests/fixtures.py` - Shared fixtures and mocks

---

## Logging Best Practices

### Structured Logging (JSON)
```python
# ✅ GOOD: Structured logging with context
import structlog

logger = structlog.get_logger()

async def download_video(url: str, task_id: str):
    logger.info(
        "download_started",
        task_id=task_id,
        url=url,  # OK to log (no PII)
        provider="youtube"
    )

    try:
        result = await perform_download(url)
        logger.info(
            "download_completed",
            task_id=task_id,
            duration_sec=result.duration,
            file_size_mb=result.size / 1024 / 1024
        )
    except Exception as e:
        logger.error(
            "download_failed",
            task_id=task_id,
            error_type=type(e).__name__,
            error_msg=str(e),
            exc_info=True
        )
        raise

# ❌ BAD: Unstructured logging
logger.info(f"Downloading {url} with task {task_id}")
```

### Log Levels
- **DEBUG**: Detailed diagnostic info (disabled in production)
- **INFO**: Normal operations (request received, task completed)
- **WARNING**: Unexpected but handled (rate limit hit, retrying)
- **ERROR**: Operation failed but service continues
- **CRITICAL**: Service-level failure (Redis down, disk full)

---

## Provider Abstraction Layer

### Interface Contract
```python
# ✅ GOOD: Clear abstract interface
from abc import ABC, abstractmethod

class BaseProvider(ABC):
    """Abstract base class for video platform providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'youtube', 'vimeo')."""
        pass

    @abstractmethod
    async def validate_url(self, url: str) -> bool:
        """Validate if URL is supported by this provider."""
        pass

    @abstractmethod
    async def extract_info(
        self,
        url: str,
        download: bool = False
    ) -> dict[str, Any]:
        """Extract video metadata and optionally download."""
        pass

    @abstractmethod
    async def get_formats(self, url: str) -> list[Format]:
        """Get available formats for video."""
        pass
```

### Implementation Guidelines
- Each provider in separate module: `app/providers/youtube.py`, etc.
- Provider registry pattern for auto-discovery
- Consistent error handling (wrap provider-specific errors)
- Unit tests for each provider with mocked responses

---

## Prohibited Patterns (Automatic Rejection)

### Security Anti-Patterns
❌ **Shell command execution with user input**
❌ **Hardcoded secrets or API keys**
❌ **Secrets in log messages**
❌ **Path concatenation without validation**
❌ **Running containers as root**
❌ **Unvalidated user input passed to yt-dlp**
❌ **Cookie files with world-readable permissions**

### Code Quality Anti-Patterns
❌ **Bare `except:` without specific exception type**
❌ **Blocking I/O in async functions** (`requests.get()`, `time.sleep()`)
❌ **Missing type hints on public functions**
❌ **Mutable default arguments** (`def func(items=[]):`)
❌ **Global mutable state without proper locking**
❌ **Print statements** (use logger instead)

### Docker Anti-Patterns
❌ **`COPY . .` before installing dependencies** (breaks layer caching)
❌ **Missing health checks**
❌ **Exposing unnecessary ports**
❌ **`latest` tag in production** (pin versions)
❌ **Running as root user**
❌ **Secrets in Dockerfile or commit history**

---

## Code Review Focus Areas

When reviewing pull requests, prioritize:

1. **Security vulnerabilities** (highest priority)
   - Path traversal, command injection, secret exposure
   - Input validation completeness
   - Authentication/authorization bypasses

2. **Docker security & optimization**
   - Multi-stage builds used correctly
   - Non-root user enforced
   - Image size reasonable (<500MB)
   - Security scanning passes (Trivy/Snyk)

3. **Async/await correctness**
   - No blocking calls in async functions
   - Proper exception handling in async contexts
   - Timeout protection on external calls

4. **Test coverage**
   - New code has corresponding tests
   - Critical paths maintain 95%+ coverage
   - Security tests for sensitive operations

5. **API contract stability**
   - Breaking changes flagged clearly
   - Backward compatibility maintained when possible
   - OpenAPI schema updated

6. **Documentation completeness**
   - Public APIs have docstrings
   - README updated if needed
   - Configuration changes documented

7. **Error handling**
   - Specific exception types caught
   - Meaningful error messages
   - Proper logging at error boundaries

---

## Git Workflow (GitFlow)

### Branch Strategy
- `main` - Production-ready code
- `develop` - Integration branch for features
- `feature/*` - New features (merge to develop via PR)
- `hotfix/*` - Critical production fixes (merge to main + develop)

### Pull Request Requirements
1. **Branch from develop**: `git checkout -b feature/add-vimeo-support develop`
2. **Make changes**: Commit with clear messages
3. **Run tests locally**: `pytest` (ensure all pass)
4. **Push and create PR**: Target `develop` branch
5. **Wait for Gemini review**: Address comments
6. **Request human review**: Tag yourself
7. **Merge when approved**: Squash commits if messy

### Commit Message Format
```
type(scope): brief description

Longer explanation if needed.

Fixes #123
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`

---

## Configuration Files Review

### config.yaml
- Environment-specific settings clearly separated
- No secrets (use environment variables)
- Sensible defaults provided
- Schema validation via Pydantic

### .env (never committed)
- Template `.env.example` committed
- All required variables documented
- Secrets use strong random values

### requirements.txt
- Exact versions pinned (`fastapi==0.104.1`)
- Security updates tracked (Dependabot enabled)
- Minimal dependencies (avoid bloat)

---

## Performance Considerations

### Rate Limiting
- Token bucket with Redis backend
- Per-client tracking (IP or API key)
- Configurable limits per endpoint
- Graceful degradation under load

### Resource Management
- Connection pooling for Redis, databases
- Async I/O throughout (no blocking operations)
- Timeout protection on all external calls
- Cleanup on failures (temp files, locks)

### Monitoring
- Prometheus metrics exposed at `/metrics`
- Key metrics: request rate, latency, error rate, active downloads
- Structured logs for aggregation (ELK/Loki)
- Health endpoint for container orchestration

---

## Questions to Always Ask During Review

1. **Security**: Could this be exploited? (path traversal, injection, DoS)
2. **Async**: Does this block the event loop?
3. **Error Handling**: What happens if this fails? Is it logged?
4. **Testing**: Are there tests? Do they cover edge cases?
5. **Documentation**: Will future-me understand this?
6. **Performance**: Could this be a bottleneck under load?
7. **Docker**: Is this image secure and optimized?

---

## Example: Ideal Pull Request

```
Title: feat(providers): Add Vimeo provider support

Description:
Implements Vimeo provider with full abstraction layer compliance.

Changes:
- New VimeoProvider class in app/providers/vimeo.py
- URL validation regex for Vimeo URLs
- Format extraction and metadata parsing
- Unit tests with mocked API responses (100% coverage)
- Integration tests for end-to-end download flow
- Updated provider registry to auto-discover Vimeo
- Documentation added to README.md

Security considerations:
- Input validation on Vimeo URLs (regex + API check)
- No new external dependencies
- Error handling for API failures

Testing:
- 23 new tests (unit + integration)
- Coverage: 98% on new code
- All existing tests pass

Checklist:
✅ Tests added and passing
✅ Documentation updated
✅ No secrets committed
✅ Type hints on all functions
✅ Follows provider interface
✅ Error handling complete
✅ Logging structured and appropriate
✅ No breaking changes to existing APIs
```

---

**This style guide is living documentation. When patterns emerge from code reviews, they should be added here for future reference.**
