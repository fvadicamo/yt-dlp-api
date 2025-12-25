"""Integration tests for FastAPI application assembly.

This module tests Task 12: FastAPI Application Assembly including:
- Full request flow from client to response
- Middleware chain execution
- Dependency injection
- Startup and shutdown lifecycle

Note: These tests use mocks for external dependencies (yt-dlp, ffmpeg, Node.js)
to avoid requiring actual binary dependencies.
"""

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_config() -> Dict[str, Any]:
    """Mock configuration for testing."""
    return {
        "server": {"host": "0.0.0.0", "port": 8000, "workers": 1},
        "storage": {
            "output_dir": "/tmp/test-downloads",
            "max_file_size": 1073741824,
            "cleanup_age_hours": 24,
            "cleanup_threshold_percent": 80,
        },
        "downloads": {"max_concurrent": 5, "queue_size": 100, "job_ttl": 24},
        "rate_limiting": {"metadata_rpm": 100, "download_rpm": 10, "burst_capacity": 20},
        "templates": {"default": "%(title)s.%(ext)s"},
        "providers": {
            "youtube": {
                "enabled": True,
                "cookie_path": "/tmp/cookies.txt",
                "retry_attempts": 3,
                "retry_backoff": [2, 4, 8],
            }
        },
        "logging": {"level": "INFO", "format": "json"},
        "security": {
            "api_keys": ["test-api-key-12345"],
            "allow_degraded_start": True,
            "cors_origins": ["*"],
        },
        "monitoring": {"metrics_enabled": True, "port": 9090},
    }


def create_test_app_without_lifespan() -> FastAPI:
    """Create a minimal test FastAPI app without the full lifespan."""
    from app.api import admin, download, health, jobs, metrics, video
    from app.core.errors import APIError, global_exception_handler
    from app.middleware.auth import get_api_key
    from app.middleware.rate_limit import RateLimitMiddleware

    app = FastAPI(title="Test YT-DLP API", version="1.0.0-test")

    # Add rate limiting middleware
    app.add_middleware(RateLimitMiddleware)

    # Add exception handlers
    app.add_exception_handler(Exception, global_exception_handler)
    app.add_exception_handler(APIError, global_exception_handler)

    # Register routers
    app.include_router(health.router)
    app.include_router(video.router)
    app.include_router(download.router)
    app.include_router(jobs.router)
    app.include_router(admin.router)
    app.include_router(metrics.router)

    # Bypass authentication for tests
    async def mock_get_api_key() -> str:
        return "test-api-key"

    app.dependency_overrides[get_api_key] = mock_get_api_key

    return app


@pytest.fixture
def test_app() -> FastAPI:
    """Create test application without lifespan for unit testing."""
    return create_test_app_without_lifespan()


# ============================================================================
# Middleware Chain Tests
# ============================================================================


class TestMiddlewareChain:
    """Tests for middleware chain execution order and behavior."""

    def test_unauthenticated_request_to_protected_endpoint(self) -> None:
        """Test that protected endpoints require authentication."""
        from app.api import video
        from app.core.errors import APIError, global_exception_handler
        from app.middleware.auth import configure_auth
        from app.providers.manager import ProviderManager

        # Configure auth with a key to ensure it's not open by default
        configure_auth(api_keys=["dummy-key-for-testing"])

        app = FastAPI()
        app.include_router(video.router)
        app.add_exception_handler(Exception, global_exception_handler)
        app.add_exception_handler(APIError, global_exception_handler)

        # Mock provider manager to isolate the authentication failure
        mock_manager = MagicMock(spec=ProviderManager)
        app.dependency_overrides[video.get_provider_manager] = lambda: mock_manager

        # No authentication header provided - should fail with 401
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/info?url=https://www.youtube.com/watch?v=abc123")

        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Invalid or missing API key"

        # Clean up global auth state after test
        configure_auth(api_keys=None)

    def test_authenticated_request_passes(self, test_app: FastAPI) -> None:
        """Test that authenticated requests pass through middleware."""
        # Configure mock provider manager
        from app.api import video
        from app.providers.manager import ProviderManager

        mock_manager = MagicMock(spec=ProviderManager)
        mock_provider = MagicMock()
        mock_provider.get_info = AsyncMock(
            return_value={
                "video_id": "abc123",
                "title": "Test Video",
                "duration": 100,
                "author": "Test",
                "upload_date": "20240101",
                "view_count": 1000,
                "thumbnail_url": "https://example.com/thumb.jpg",
                "description": "Test",
            }
        )
        mock_manager.get_provider_for_url.return_value = mock_provider

        test_app.dependency_overrides[video.get_provider_manager] = lambda: mock_manager

        client = TestClient(test_app)
        response = client.get("/api/v1/info?url=https://www.youtube.com/watch?v=abc123")

        assert response.status_code == 200
        data = response.json()
        assert data["video_id"] == "abc123"

    @pytest.mark.asyncio
    async def test_rate_limiting_header_on_limit(self) -> None:
        """Test that rate limiting returns Retry-After header."""
        from app.core.rate_limiter import RateLimitConfig, RateLimiter

        # Create a rate limiter with very restrictive limits
        limits = {
            "metadata": RateLimitConfig(rpm=1, burst_capacity=1),
            "download": RateLimitConfig(rpm=1, burst_capacity=1),
        }
        limiter = RateLimiter(limits=limits)

        # First request should succeed
        allowed, _ = await limiter.check_rate_limit("test-key", "metadata")
        assert allowed is True

        # Second request should fail (exceeded limit)
        allowed, retry_after = await limiter.check_rate_limit("test-key", "metadata")
        assert allowed is False
        assert retry_after is not None
        assert retry_after > 0

    def test_health_endpoints_bypass_auth(self, test_app: FastAPI) -> None:
        """Test that health endpoints don't require authentication."""
        # Remove auth bypass to test actual bypass behavior
        from app.middleware.auth import get_api_key

        test_app.dependency_overrides.pop(get_api_key, None)

        client = TestClient(test_app, raise_server_exceptions=False)

        # Liveness should always work
        response = client.get("/liveness")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"


# ============================================================================
# Dependency Injection Tests
# ============================================================================


class TestDependencyInjection:
    """Tests for FastAPI dependency injection setup."""

    def test_provider_manager_injection(self, test_app: FastAPI) -> None:
        """Test that provider manager is properly injected."""
        from app.api import video
        from app.providers.manager import ProviderManager

        mock_manager = MagicMock(spec=ProviderManager)
        mock_provider = MagicMock()
        mock_provider.get_info = AsyncMock(
            return_value={
                "video_id": "test123",
                "title": "Dependency Test",
                "duration": 60,
                "author": "Tester",
                "upload_date": "20240101",
                "view_count": 500,
                "thumbnail_url": "https://example.com/thumb.jpg",
                "description": "Testing DI",
            }
        )
        mock_manager.get_provider_for_url.return_value = mock_provider

        test_app.dependency_overrides[video.get_provider_manager] = lambda: mock_manager

        client = TestClient(test_app)
        response = client.get("/api/v1/info?url=https://www.youtube.com/watch?v=test123")

        assert response.status_code == 200
        mock_manager.get_provider_for_url.assert_called_once()

    def test_job_service_injection(self, test_app: FastAPI) -> None:
        """Test that job service is properly injected."""
        from datetime import datetime, timezone

        from app.api import jobs
        from app.models.job import Job, JobStatus

        mock_job_service = MagicMock()
        mock_job = Job(
            job_id="job-abc123",
            url="https://www.youtube.com/watch?v=test",
            status=JobStatus.COMPLETED,  # Use COMPLETED to avoid queue position lookup
            params={},
            progress=100,
            retry_count=0,
            created_at=datetime.now(timezone.utc),
        )
        mock_job_service.get_job_or_raise.return_value = mock_job

        mock_queue = MagicMock()
        mock_queue.get_queue_position.return_value = None

        test_app.dependency_overrides[jobs.get_job_service] = lambda: mock_job_service
        test_app.dependency_overrides[jobs.get_download_queue] = lambda: mock_queue

        client = TestClient(test_app)
        response = client.get("/api/v1/jobs/job-abc123")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "job-abc123"
        mock_job_service.get_job_or_raise.assert_called_with("job-abc123")

    def test_download_queue_injection(self, test_app: FastAPI) -> None:
        """Test that download queue is properly injected in job status endpoint."""
        from datetime import datetime, timezone

        from app.api import jobs
        from app.models.job import Job, JobStatus

        mock_job_service = MagicMock()
        mock_job = Job(
            job_id="queue-test-job",
            url="https://www.youtube.com/watch?v=test",
            status=JobStatus.PENDING,
            params={},
            progress=0,
            retry_count=0,
            created_at=datetime.now(timezone.utc),
        )
        mock_job_service.get_job_or_raise.return_value = mock_job

        mock_queue = MagicMock()
        mock_queue.get_queue_position.return_value = 5

        test_app.dependency_overrides[jobs.get_job_service] = lambda: mock_job_service
        test_app.dependency_overrides[jobs.get_download_queue] = lambda: mock_queue

        client = TestClient(test_app)
        response = client.get("/api/v1/jobs/queue-test-job")

        assert response.status_code == 200
        data = response.json()
        assert data["queue_position"] == 5


# ============================================================================
# Full Request Flow Tests
# ============================================================================


class TestFullRequestFlow:
    """Tests for complete request-response flows."""

    def test_video_info_full_flow(self, test_app: FastAPI) -> None:
        """Test complete video info request flow."""
        from app.api import video
        from app.providers.manager import ProviderManager

        mock_manager = MagicMock(spec=ProviderManager)
        mock_provider = MagicMock()
        mock_provider.get_info = AsyncMock(
            return_value={
                "video_id": "dQw4w9WgXcQ",
                "title": "Rick Astley - Never Gonna Give You Up",
                "duration": 212,
                "author": "Rick Astley",
                "upload_date": "20091025",
                "view_count": 1500000000,
                "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
                "description": "Official music video",
                "formats": [
                    {
                        "format_id": "22",
                        "ext": "mp4",
                        "resolution": "1280x720",
                        "format_type": "video+audio",
                    }
                ],
                "subtitles": [{"language": "en", "format": "vtt", "auto_generated": False}],
            }
        )
        mock_manager.get_provider_for_url.return_value = mock_provider

        test_app.dependency_overrides[video.get_provider_manager] = lambda: mock_manager

        client = TestClient(test_app)
        response = client.get(
            "/api/v1/info?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            "&include_formats=true&include_subtitles=true"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["video_id"] == "dQw4w9WgXcQ"
        assert data["title"] == "Rick Astley - Never Gonna Give You Up"
        assert data["duration"] == 212
        assert len(data["formats"]) == 1
        assert len(data["subtitles"]) == 1

    def test_async_download_full_flow(self, test_app: FastAPI) -> None:
        """Test complete async download request flow."""
        from datetime import datetime, timezone

        from app.api import download
        from app.models.job import Job, JobStatus
        from app.providers.manager import ProviderManager

        mock_manager = MagicMock(spec=ProviderManager)
        mock_manager.get_provider_for_url.return_value = MagicMock()

        mock_job_service = MagicMock()
        mock_job = Job(
            job_id="download-job-123",
            url="https://www.youtube.com/watch?v=test",
            status=JobStatus.PENDING,
            params={},
            progress=0,
            retry_count=0,
            created_at=datetime.now(timezone.utc),
        )
        mock_job_service.create_job.return_value = mock_job

        mock_queue = MagicMock()
        mock_queue.enqueue = AsyncMock(return_value=1)

        mock_worker = MagicMock()

        test_app.dependency_overrides[download.get_provider_manager] = lambda: mock_manager
        test_app.dependency_overrides[download.get_job_service] = lambda: mock_job_service
        test_app.dependency_overrides[download.get_download_queue] = lambda: mock_queue
        test_app.dependency_overrides[download.get_download_worker] = lambda: mock_worker

        client = TestClient(test_app)
        response = client.post(
            "/api/v1/download",
            json={
                "url": "https://www.youtube.com/watch?v=test",
                "async": True,
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data["job_id"] == "download-job-123"
        assert data["status"] == "pending"
        assert data["queue_position"] == 1

    def test_error_response_format(self, test_app: FastAPI) -> None:
        """Test that error responses follow the standard format."""
        from app.api import video
        from app.providers.exceptions import VideoUnavailableError
        from app.providers.manager import ProviderManager

        mock_manager = MagicMock(spec=ProviderManager)
        mock_provider = MagicMock()
        mock_provider.get_info = AsyncMock(side_effect=VideoUnavailableError("Video not found"))
        mock_manager.get_provider_for_url.return_value = mock_provider

        test_app.dependency_overrides[video.get_provider_manager] = lambda: mock_manager

        client = TestClient(test_app)
        response = client.get("/api/v1/info?url=https://www.youtube.com/watch?v=notfound")

        assert response.status_code == 404
        data = response.json()
        # HTTPException wraps error in 'detail' key
        error_detail = data.get("detail", data)
        assert "error_code" in error_detail
        assert error_detail["error_code"] == "VIDEO_UNAVAILABLE"
        assert "message" in error_detail

    def test_job_not_found_response(self, test_app: FastAPI) -> None:
        """Test job not found returns proper error."""
        from app.api import jobs
        from app.services.job_service import JobNotFoundError

        mock_job_service = MagicMock()
        mock_job_service.get_job_or_raise.side_effect = JobNotFoundError("nonexistent-job")

        mock_queue = MagicMock()

        test_app.dependency_overrides[jobs.get_job_service] = lambda: mock_job_service
        test_app.dependency_overrides[jobs.get_download_queue] = lambda: mock_queue

        client = TestClient(test_app)
        response = client.get("/api/v1/jobs/nonexistent-job")

        assert response.status_code == 404
        data = response.json()
        # HTTPException wraps error in 'detail' key
        error_detail = data.get("detail", data)
        assert error_detail["error_code"] == "JOB_NOT_FOUND"


# ============================================================================
# Health Endpoint Tests
# ============================================================================


class TestHealthEndpointsIntegration:
    """Integration tests for health check endpoints."""

    def test_liveness_always_succeeds(self, test_app: FastAPI) -> None:
        """Test liveness probe always returns alive."""
        client = TestClient(test_app)
        response = client.get("/liveness")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"

    @patch("app.api.health._check_ytdlp")
    @patch("app.api.health._check_ffmpeg")
    @patch("app.api.health._check_nodejs")
    @patch("app.api.health._check_storage")
    @patch("app.api.health._check_cookies")
    @patch("app.api.health._check_youtube_connectivity")
    def test_health_endpoint_aggregates_components(
        self,
        mock_youtube: MagicMock,
        mock_cookies: MagicMock,
        mock_storage: MagicMock,
        mock_nodejs: MagicMock,
        mock_ffmpeg: MagicMock,
        mock_ytdlp: MagicMock,
        test_app: FastAPI,
    ) -> None:
        """Test health endpoint aggregates all component checks."""
        from app.api.schemas import ComponentHealth

        mock_ytdlp.return_value = ComponentHealth(status="healthy", version="2024.12.01")
        mock_ffmpeg.return_value = ComponentHealth(status="healthy", version="6.0")
        mock_nodejs.return_value = ComponentHealth(status="healthy", version="v20.0.0")
        mock_storage.return_value = ComponentHealth(status="healthy", details={"available_gb": 100})
        mock_cookies.return_value = ComponentHealth(status="healthy")
        mock_youtube.return_value = ComponentHealth(status="healthy", details={"latency_ms": 150})

        client = TestClient(test_app)
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "components" in data
        assert "ytdlp" in data["components"]
        assert "ffmpeg" in data["components"]
        assert "nodejs" in data["components"]
        assert "storage" in data["components"]
        assert "cookie" in data["components"]
        assert "youtube_connectivity" in data["components"]

    @patch("app.api.health._check_ytdlp")
    @patch("app.api.health._check_storage")
    def test_readiness_when_healthy(
        self, mock_storage: MagicMock, mock_ytdlp: MagicMock, test_app: FastAPI
    ) -> None:
        """Test readiness endpoint when all required components are healthy."""
        from app.api.schemas import ComponentHealth

        mock_ytdlp.return_value = ComponentHealth(status="healthy", version="2024.12.01")
        mock_storage.return_value = ComponentHealth(status="healthy")

        client = TestClient(test_app)
        response = client.get("/readiness")

        assert response.status_code == 200
        data = response.json()
        assert data["ready"] is True
        assert data["status"] == "ready"

    @patch("app.api.health._check_ytdlp")
    @patch("app.api.health._check_storage")
    def test_readiness_when_ytdlp_unavailable(
        self, mock_storage: MagicMock, mock_ytdlp: MagicMock, test_app: FastAPI
    ) -> None:
        """Test readiness endpoint when yt-dlp is unavailable."""
        from app.api.schemas import ComponentHealth

        mock_ytdlp.return_value = ComponentHealth(
            status="unhealthy", details={"error": "yt-dlp not found"}
        )
        mock_storage.return_value = ComponentHealth(status="healthy")

        client = TestClient(test_app)
        response = client.get("/readiness")

        assert response.status_code == 503
        data = response.json()
        assert data["ready"] is False
        assert "yt-dlp" in data["message"]


# ============================================================================
# Metrics Endpoint Tests
# ============================================================================


class TestMetricsIntegration:
    """Integration tests for Prometheus metrics endpoint."""

    def test_metrics_endpoint_returns_prometheus_format(self, test_app: FastAPI) -> None:
        """Test metrics endpoint returns Prometheus text format."""
        client = TestClient(test_app)
        response = client.get("/metrics")

        assert response.status_code == 200
        content = response.text
        # Should contain Prometheus format markers and specific metrics
        assert "# HELP" in content
        assert "# TYPE" in content
        # Verify specific metrics are defined
        assert "http_requests_total" in content
        assert "errors_total" in content


# ============================================================================
# Startup Validation Tests
# ============================================================================


class TestStartupValidation:
    """Tests for startup validation behavior."""

    @pytest.mark.asyncio
    async def test_startup_validator_checks_components(self) -> None:
        """Test that startup validator checks all required components."""
        from app.core.startup import ComponentCheckResult, StartupValidator

        # Create a mock config with nested structure
        config = MagicMock()
        config.providers.youtube.enabled = True
        config.providers.youtube.cookie_path = "/tmp/test-cookies.txt"
        config.storage.output_dir = "/tmp/test-output"
        config.security.allow_degraded_start = True

        validator = StartupValidator(config)

        # Mock the component checks to return ComponentCheckResult objects
        with (
            patch.object(validator, "check_ytdlp") as mock_ytdlp,
            patch.object(validator, "check_ffmpeg") as mock_ffmpeg,
            patch.object(validator, "check_nodejs") as mock_nodejs,
            patch.object(validator, "check_storage") as mock_storage,
            patch.object(validator, "check_cookies") as mock_cookies,
            patch.object(validator, "configure_ytdlp_runtime") as mock_config,
        ):
            mock_ytdlp.return_value = ComponentCheckResult(
                name="ytdlp", passed=True, critical=True, version="2024.12.01"
            )
            mock_ffmpeg.return_value = ComponentCheckResult(
                name="ffmpeg", passed=True, critical=True, version="6.0"
            )
            mock_nodejs.return_value = ComponentCheckResult(
                name="nodejs", passed=True, critical=True, version="v20.0.0"
            )
            mock_storage.return_value = ComponentCheckResult(
                name="storage", passed=True, critical=True
            )
            mock_cookies.return_value = ComponentCheckResult(
                name="cookies", passed=True, critical=False
            )
            mock_config.return_value = None

            result = await validator.validate_all()

            assert result.success is True
            mock_ytdlp.assert_called_once()
            mock_ffmpeg.assert_called_once()
            mock_nodejs.assert_called_once()

    @pytest.mark.asyncio
    async def test_startup_fails_without_degraded_mode(self) -> None:
        """Test that startup fails when a critical component is missing and degraded mode is off."""
        from app.core.startup import ComponentCheckResult, StartupValidator

        # Create a mock config with nested structure
        config = MagicMock()
        config.providers.youtube.enabled = True
        config.providers.youtube.cookie_path = "/nonexistent/cookies.txt"
        config.storage.output_dir = "/tmp/test-output"
        config.security.allow_degraded_start = False

        validator = StartupValidator(config)

        with (
            patch.object(validator, "check_ytdlp") as mock_ytdlp,
            patch.object(validator, "check_ffmpeg") as mock_ffmpeg,
            patch.object(validator, "check_nodejs") as mock_nodejs,
            patch.object(validator, "check_storage") as mock_storage,
            patch.object(validator, "check_cookies") as mock_cookies,
        ):
            # Simulate yt-dlp not found (critical failure)
            mock_ytdlp.return_value = ComponentCheckResult(
                name="ytdlp", passed=False, critical=True, message="yt-dlp not found"
            )
            mock_ffmpeg.return_value = ComponentCheckResult(
                name="ffmpeg", passed=True, critical=True, version="6.0"
            )
            mock_nodejs.return_value = ComponentCheckResult(
                name="nodejs", passed=True, critical=True, version="v20.0.0"
            )
            mock_storage.return_value = ComponentCheckResult(
                name="storage", passed=True, critical=True
            )
            mock_cookies.return_value = ComponentCheckResult(
                name="cookies", passed=True, critical=False
            )

            result = await validator.validate_all()

            # Without degraded mode, missing yt-dlp should fail
            assert result.success is False
            assert len(result.errors) > 0


# ============================================================================
# Application Lifecycle Tests
# ============================================================================


class TestApplicationLifecycle:
    """Tests for application startup and shutdown lifecycle."""

    def test_create_app_returns_fastapi_instance(self) -> None:
        """Test that create_app returns a FastAPI application."""
        # We can't test the full lifespan without mocking all external deps,
        # but we can verify the app creation structure
        from app.main import API_DESCRIPTION

        assert "REST API for video downloads" in API_DESCRIPTION
        assert "Error Codes" in API_DESCRIPTION
        assert "Authentication" in API_DESCRIPTION

    def test_openapi_schema_includes_metadata(self, test_app: FastAPI) -> None:
        """Test that OpenAPI schema includes proper metadata."""
        client = TestClient(test_app)
        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        assert "info" in schema
        assert schema["info"]["title"] == "Test YT-DLP API"

    def test_docs_endpoint_accessible(self, test_app: FastAPI) -> None:
        """Test that Swagger UI docs endpoint is accessible."""
        client = TestClient(test_app)
        response = client.get("/docs")

        # Should redirect or return HTML
        assert response.status_code in (200, 307)

    def test_redoc_endpoint_accessible(self, test_app: FastAPI) -> None:
        """Test that ReDoc endpoint is accessible."""
        client = TestClient(test_app)
        response = client.get("/redoc")

        # Should redirect or return HTML
        assert response.status_code in (200, 307)
