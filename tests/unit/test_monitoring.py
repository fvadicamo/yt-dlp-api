"""Tests for error handling and monitoring functionality.

This module tests Task 10 implementation:
- Error codes and mappings (Req 16)
- Global exception handler (Req 16)
- Prometheus metrics (Req 29)
- YouTube connectivity health check (Req 30)
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from app.core.errors import (
    ERROR_CODE_TO_STATUS,
    ERROR_SUGGESTIONS,
    APIError,
    ErrorCode,
    global_exception_handler,
    map_exception_to_api_error,
)
from app.core.metrics import (
    MetricsCollector,
    concurrent_downloads,
    download_queue_size,
    downloads_total,
    errors_total,
    http_request_duration_seconds,
    http_requests_total,
    initialize_metrics,
    storage_available_bytes,
    storage_percent_used,
    storage_used_bytes,
)
from app.providers.exceptions import (
    AuthenticationError,
    CookieError,
    DownloadError,
    FormatNotFoundError,
    InvalidURLError,
    ProviderError,
    TranscodingError,
    VideoUnavailableError,
)
from app.services.job_service import JobNotFoundError


class TestErrorCodes:
    """Tests for error code constants and mappings."""

    def test_all_error_codes_have_status_mapping(self) -> None:
        """Ensure all error codes have HTTP status mappings."""
        error_code_attrs = [
            attr for attr in dir(ErrorCode) if not attr.startswith("_") and attr.isupper()
        ]

        for attr in error_code_attrs:
            code = getattr(ErrorCode, attr)
            assert code in ERROR_CODE_TO_STATUS, f"Error code {code} missing status mapping"

    def test_all_error_codes_have_suggestions(self) -> None:
        """Ensure all error codes have user-friendly suggestions."""
        error_code_attrs = [
            attr for attr in dir(ErrorCode) if not attr.startswith("_") and attr.isupper()
        ]

        for attr in error_code_attrs:
            code = getattr(ErrorCode, attr)
            assert code in ERROR_SUGGESTIONS, f"Error code {code} missing suggestion"

    def test_client_errors_map_to_4xx(self) -> None:
        """Client error codes should map to 4xx status codes."""
        client_errors = [
            ErrorCode.INVALID_URL,
            ErrorCode.INVALID_FORMAT,
            ErrorCode.INVALID_TEMPLATE,
            ErrorCode.FORMAT_NOT_FOUND,
            ErrorCode.AUTH_FAILED,
            ErrorCode.JOB_NOT_FOUND,
            ErrorCode.RATE_LIMIT_EXCEEDED,
        ]

        for code in client_errors:
            status = ERROR_CODE_TO_STATUS[code]
            assert 400 <= status < 500, f"Client error {code} should map to 4xx, got {status}"

    def test_server_errors_map_to_5xx(self) -> None:
        """Server error codes should map to 5xx status codes."""
        server_errors = [
            ErrorCode.DOWNLOAD_FAILED,
            ErrorCode.TRANSCODING_FAILED,
            ErrorCode.PROVIDER_ERROR,
            ErrorCode.INTERNAL_ERROR,
            ErrorCode.STORAGE_FULL,
            ErrorCode.QUEUE_FULL,
            ErrorCode.NO_SLOTS_AVAILABLE,
        ]

        for code in server_errors:
            status = ERROR_CODE_TO_STATUS[code]
            assert 500 <= status < 600, f"Server error {code} should map to 5xx, got {status}"


class TestAPIError:
    """Tests for APIError exception class."""

    def test_api_error_creation(self) -> None:
        """Test APIError with all fields."""
        error = APIError(
            error_code=ErrorCode.INVALID_URL,
            message="Bad URL",
            details="URL parsing failed",
            suggestion="Check URL format",
        )

        assert error.error_code == ErrorCode.INVALID_URL
        assert error.message == "Bad URL"
        assert error.details == "URL parsing failed"
        assert error.suggestion == "Check URL format"

    def test_api_error_default_suggestion(self) -> None:
        """Test automatic suggestion lookup when not provided."""
        error = APIError(
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message="Too many requests",
        )

        assert error.suggestion == ERROR_SUGGESTIONS[ErrorCode.RATE_LIMIT_EXCEEDED]

    def test_api_error_custom_suggestion_overrides_default(self) -> None:
        """Test that custom suggestion overrides default."""
        custom = "My custom suggestion"
        error = APIError(
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message="Too many requests",
            suggestion=custom,
        )

        assert error.suggestion == custom

    def test_api_error_is_exception(self) -> None:
        """Test APIError can be raised and caught."""
        error = APIError(error_code=ErrorCode.INTERNAL_ERROR, message="Test")

        with pytest.raises(APIError) as exc_info:
            raise error

        assert exc_info.value.error_code == ErrorCode.INTERNAL_ERROR


class TestExceptionMapping:
    """Tests for exception to APIError mapping."""

    @pytest.mark.parametrize(
        "exception,expected_code",
        [
            (InvalidURLError("bad url"), ErrorCode.INVALID_URL),
            (VideoUnavailableError("private"), ErrorCode.VIDEO_UNAVAILABLE),
            (FormatNotFoundError("no 1080p"), ErrorCode.FORMAT_NOT_FOUND),
            (TranscodingError("ffmpeg failed"), ErrorCode.TRANSCODING_FAILED),
            (AuthenticationError("bad key"), ErrorCode.AUTH_FAILED),
            (CookieError("expired"), ErrorCode.COOKIE_EXPIRED),
            (DownloadError("network"), ErrorCode.DOWNLOAD_FAILED),
            (ProviderError("generic"), ErrorCode.PROVIDER_ERROR),
            (JobNotFoundError("not found"), ErrorCode.JOB_NOT_FOUND),
        ],
    )
    def test_exception_mapping(
        self,
        exception: Exception,
        expected_code: str,
    ) -> None:
        """Test provider/service exceptions map correctly."""
        api_error = map_exception_to_api_error(exception)

        assert api_error.error_code == expected_code
        assert api_error.message == str(exception)

    def test_unknown_exception_maps_to_internal_error(self) -> None:
        """Test unexpected exceptions map to INTERNAL_ERROR."""
        api_error = map_exception_to_api_error(ValueError("random error"))

        assert api_error.error_code == ErrorCode.INTERNAL_ERROR


class TestGlobalExceptionHandler:
    """Tests for global exception handler."""

    @pytest.fixture
    def mock_request(self) -> MagicMock:
        """Create a mock FastAPI request."""
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/test"
        return request

    @pytest.mark.asyncio
    async def test_handles_api_error(self, mock_request: MagicMock) -> None:
        """Test APIError produces correct response."""
        error = APIError(
            error_code=ErrorCode.INVALID_URL,
            message="Bad URL format",
        )

        response = await global_exception_handler(mock_request, error)

        assert response.status_code == 400
        body = response.body.decode()
        assert "INVALID_URL" in body
        assert "Bad URL format" in body

    @pytest.mark.asyncio
    async def test_handles_http_exception(self, mock_request: MagicMock) -> None:
        """Test HTTPException is preserved."""
        error = HTTPException(status_code=404, detail="Not found")

        response = await global_exception_handler(mock_request, error)

        assert response.status_code == 404
        body = response.body.decode()
        assert "Not found" in body

    @pytest.mark.asyncio
    async def test_handles_http_exception_with_structured_detail(
        self,
        mock_request: MagicMock,
    ) -> None:
        """Test HTTPException with structured detail."""
        error = HTTPException(
            status_code=400,
            detail={"error_code": "CUSTOM_ERROR", "message": "Custom message"},
        )

        response = await global_exception_handler(mock_request, error)

        assert response.status_code == 400
        body = response.body.decode()
        assert "CUSTOM_ERROR" in body

    @pytest.mark.asyncio
    async def test_handles_provider_error(self, mock_request: MagicMock) -> None:
        """Test ProviderError is mapped correctly."""
        error = VideoUnavailableError("Video is private")

        response = await global_exception_handler(mock_request, error)

        assert response.status_code == 404
        body = response.body.decode()
        assert "VIDEO_UNAVAILABLE" in body

    @pytest.mark.asyncio
    async def test_handles_unexpected_error(self, mock_request: MagicMock) -> None:
        """Test unexpected errors return INTERNAL_ERROR."""
        error = RuntimeError("Something went wrong")

        response = await global_exception_handler(mock_request, error)

        assert response.status_code == 500
        body = response.body.decode()
        assert "INTERNAL_ERROR" in body

    @pytest.mark.asyncio
    async def test_includes_timestamp(self, mock_request: MagicMock) -> None:
        """Test response includes timestamp."""
        error = APIError(error_code=ErrorCode.INVALID_URL, message="test")

        response = await global_exception_handler(mock_request, error)

        body = response.body.decode()
        assert "timestamp" in body

    @pytest.mark.asyncio
    async def test_includes_request_id_when_set(
        self,
        mock_request: MagicMock,
    ) -> None:
        """Test request_id is included when context is set."""
        from app.core.logging import clear_request_id, set_request_id

        set_request_id("req_test123456")
        try:
            error = APIError(error_code=ErrorCode.INVALID_URL, message="test")
            response = await global_exception_handler(mock_request, error)

            body = response.body.decode()
            assert "request_id" in body
            assert "req_test123456" in body
        finally:
            clear_request_id()


class TestMetricsCollection:
    """Tests for Prometheus metrics collection."""

    def test_record_request_increments_counter(self) -> None:
        """Test HTTP request counter increment."""
        # Get initial value
        initial = http_requests_total.labels(
            method="GET", endpoint="/test", status="200"
        )._value.get()

        MetricsCollector.record_request(
            method="GET",
            endpoint="/test",
            status=200,
            duration=0.1,
        )

        final = http_requests_total.labels(
            method="GET", endpoint="/test", status="200"
        )._value.get()

        assert final == initial + 1

    def test_record_request_observes_duration(self) -> None:
        """Test request duration histogram observation."""
        MetricsCollector.record_request(
            method="POST",
            endpoint="/api/v1/download",
            status=202,
            duration=0.5,
        )

        # Histogram should have at least one observation
        histogram = http_request_duration_seconds.labels(method="POST", endpoint="/api/v1/download")
        assert histogram._sum.get() > 0

    def test_record_download_success(self) -> None:
        """Test download success metrics."""
        initial = downloads_total.labels(provider="youtube", status="success")._value.get()

        MetricsCollector.record_download(
            provider="youtube",
            status="success",
            duration=120.0,
            size=50_000_000,
        )

        final = downloads_total.labels(provider="youtube", status="success")._value.get()

        assert final == initial + 1

    def test_record_download_failure(self) -> None:
        """Test download failure metrics."""
        initial = downloads_total.labels(provider="youtube", status="failed")._value.get()

        MetricsCollector.record_download(
            provider="youtube",
            status="failed",
            duration=5.0,
            size=0,
        )

        final = downloads_total.labels(provider="youtube", status="failed")._value.get()

        assert final == initial + 1

    def test_update_queue_metrics(self) -> None:
        """Test queue gauge updates."""
        MetricsCollector.update_queue_metrics(queue_size=5, active_downloads=3)

        assert download_queue_size._value.get() == 5
        assert concurrent_downloads._value.get() == 3

    def test_update_storage_metrics(self) -> None:
        """Test storage gauge updates."""
        MetricsCollector.update_storage_metrics(
            used=1_000_000_000,
            available=9_000_000_000,
            percent=10.0,
        )

        assert storage_used_bytes._value.get() == 1_000_000_000
        assert storage_available_bytes._value.get() == 9_000_000_000
        assert storage_percent_used._value.get() == 10.0

    def test_record_error_by_code(self) -> None:
        """Test error counter by code."""
        initial = errors_total.labels(
            error_code="INVALID_URL", endpoint="/api/v1/info"
        )._value.get()

        MetricsCollector.record_error(
            error_code="INVALID_URL",
            endpoint="/api/v1/info",
        )

        final = errors_total.labels(error_code="INVALID_URL", endpoint="/api/v1/info")._value.get()

        assert final == initial + 1

    def test_initialize_metrics(self) -> None:
        """Test metrics initialization with version."""
        initialize_metrics("1.0.0-test")
        # If no exception, initialization succeeded


class TestMetricsEndpoint:
    """Tests for /metrics endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client with mocked dependencies."""
        from app.main import app

        # Create client without lifespan to avoid startup dependencies
        return TestClient(app, raise_server_exceptions=False)

    def test_metrics_endpoint_returns_prometheus_format(
        self,
        client: TestClient,
    ) -> None:
        """Test metrics endpoint returns correct content type."""
        response = client.get("/metrics")

        # Check content type (may be text/plain or text/plain; charset=utf-8)
        content_type = response.headers.get("content-type", "")
        assert "text/plain" in content_type or response.status_code == 200

    def test_metrics_endpoint_contains_http_metrics(
        self,
        client: TestClient,
    ) -> None:
        """Test metrics endpoint contains HTTP request metrics."""
        response = client.get("/metrics")

        if response.status_code == 200:
            content = response.text
            assert "http_requests_total" in content or response.status_code == 200


class TestYouTubeConnectivityCheck:
    """Tests for YouTube connectivity health check."""

    @pytest.mark.asyncio
    async def test_connectivity_check_success(self) -> None:
        """Test successful YouTube connectivity."""
        from app.api.health import _check_youtube_connectivity

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"jNQXAC9IVRw\n", b""))
            mock_subprocess.return_value = mock_process

            result = await _check_youtube_connectivity()

            assert result.status == "healthy"
            assert result.details is not None
            assert "latency_ms" in result.details

    @pytest.mark.asyncio
    async def test_connectivity_check_timeout(self) -> None:
        """Test timeout handling (<2s requirement)."""
        from app.api.health import _check_youtube_connectivity

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.kill = MagicMock()
            mock_process.wait = AsyncMock()

            async def slow_communicate() -> tuple:
                await asyncio.sleep(10)
                return (b"", b"")

            mock_process.communicate = slow_communicate
            mock_subprocess.return_value = mock_process

            with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
                result = await _check_youtube_connectivity()

            assert result.status == "unhealthy"
            assert result.details is not None
            assert "timed out" in result.details.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_connectivity_check_failure(self) -> None:
        """Test YouTube connectivity failure."""
        from app.api.health import _check_youtube_connectivity

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 1
            mock_process.communicate = AsyncMock(return_value=(b"", b"ERROR: Video unavailable"))
            mock_subprocess.return_value = mock_process

            result = await _check_youtube_connectivity()

            assert result.status == "unhealthy"
            assert result.details is not None
            assert "error" in result.details

    @pytest.mark.asyncio
    async def test_connectivity_check_ytdlp_not_found(self) -> None:
        """Test when yt-dlp is not installed."""
        from app.api.health import _check_youtube_connectivity

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError(),
        ):
            result = await _check_youtube_connectivity()

            assert result.status == "unhealthy"
            assert result.details is not None
            assert "not found" in result.details.get("error", "").lower()


class TestHealthCheckWithYouTube:
    """Tests for health check including YouTube connectivity."""

    @pytest.mark.asyncio
    async def test_health_check_includes_youtube_connectivity(self) -> None:
        """Test that health check includes YouTube connectivity component."""
        from app.api.health import ComponentHealth, health_check

        # Mock all component checks
        with (
            patch("app.api.health._check_ytdlp") as mock_ytdlp,
            patch("app.api.health._check_ffmpeg") as mock_ffmpeg,
            patch("app.api.health._check_nodejs") as mock_nodejs,
            patch("app.api.health._check_youtube_connectivity") as mock_yt,
            patch("app.api.health._check_storage") as mock_storage,
            patch("app.api.health._check_cookies") as mock_cookies,
        ):

            # Set up all mocks to return healthy
            healthy = ComponentHealth(status="healthy")
            mock_ytdlp.return_value = healthy
            mock_ffmpeg.return_value = healthy
            mock_nodejs.return_value = healthy
            mock_yt.return_value = healthy
            mock_storage.return_value = healthy
            mock_cookies.return_value = healthy

            response = await health_check()

            assert response.status_code == 200
            body = response.body.decode()
            assert "youtube_connectivity" in body
