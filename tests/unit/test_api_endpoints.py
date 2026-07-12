"""Tests for API endpoints.

This module tests the API endpoints implementation (Task 9).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import download, health, jobs, transcript, video
from app.middleware.auth import get_api_key
from app.models.job import Job, JobStatus
from app.models.video import VideoFormat
from app.providers.exceptions import ProviderError, VideoUnavailableError
from app.providers.manager import ProviderManager

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def app() -> FastAPI:
    """Create a test FastAPI application with auth bypass."""
    app = FastAPI()
    app.include_router(health.router)
    app.include_router(video.router)
    app.include_router(transcript.router)
    app.include_router(download.router)
    app.include_router(jobs.router)

    # Bypass authentication for tests
    async def mock_get_api_key() -> str:
        return "test-api-key"

    app.dependency_overrides[get_api_key] = mock_get_api_key

    return app


@pytest.fixture
def mock_provider_manager() -> MagicMock:
    """Create a mock provider manager."""
    manager = MagicMock(spec=ProviderManager)
    return manager


@pytest.fixture
def mock_job_service() -> MagicMock:
    """Create a mock job service."""
    service = MagicMock()
    return service


@pytest.fixture
def mock_download_queue() -> MagicMock:
    """Create a mock download queue."""
    queue = MagicMock()
    queue.enqueue = AsyncMock(return_value=1)
    queue.get_queue_position = MagicMock(return_value=1)
    queue.acquire_slot_for_sync = AsyncMock(return_value=True)
    queue.release_slot = AsyncMock()
    return queue


@pytest.fixture
def mock_download_worker() -> MagicMock:
    """Create a mock download worker."""
    worker = MagicMock()
    worker.process_single_job = AsyncMock()
    return worker


@pytest.fixture
def sample_video_info() -> dict:
    """Sample video info response."""
    return {
        "video_id": "abc123",
        "title": "Test Video",
        "duration": 120,
        "author": "Test Author",
        "upload_date": "20240101",
        "view_count": 1000,
        "thumbnail_url": "https://example.com/thumb.jpg",
        "description": "Test description",
    }


@pytest.fixture
def sample_job() -> Job:
    """Create a sample job."""
    from datetime import datetime, timezone

    return Job(
        job_id="job-123",
        url="https://www.youtube.com/watch?v=abc123",
        status=JobStatus.PENDING,
        params={},
        progress=0,
        retry_count=0,
        max_retries=3,
        error_message=None,
        file_path=None,
        file_size=None,
        duration=None,
        created_at=datetime.now(timezone.utc),
        started_at=None,
        completed_at=None,
        queue_position=1,
    )


# ============================================================================
# Health Check Endpoint Tests
# ============================================================================


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_liveness_returns_alive(self, app: FastAPI) -> None:
        """Test liveness endpoint returns alive status."""
        client = TestClient(app)
        response = client.get("/liveness")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"

    @patch("app.api.health._check_ytdlp")
    @patch("app.api.health._check_ffmpeg")
    @patch("app.api.health._check_nodejs")
    @patch("app.api.health._check_youtube_connectivity")
    @patch("app.api.health._check_storage")
    @patch("app.api.health._check_cookies")
    def test_health_all_healthy(
        self,
        mock_cookies: MagicMock,
        mock_storage: MagicMock,
        mock_youtube: MagicMock,
        mock_nodejs: MagicMock,
        mock_ffmpeg: MagicMock,
        mock_ytdlp: MagicMock,
        app: FastAPI,
    ) -> None:
        """Test health endpoint when all components healthy."""
        from app.api.schemas import ComponentHealth

        mock_ytdlp.return_value = ComponentHealth(status="healthy", version="2024.01.01")
        mock_ffmpeg.return_value = ComponentHealth(status="healthy", version="6.0")
        mock_nodejs.return_value = ComponentHealth(status="healthy", version="v20.0.0")
        mock_youtube.return_value = ComponentHealth(status="healthy", details={"latency_ms": 500})
        mock_storage.return_value = ComponentHealth(
            status="healthy", details={"available_gb": 100.0, "used_percent": 50.0}
        )
        mock_cookies.return_value = ComponentHealth(
            status="healthy", details={"youtube": {"exists": True}}
        )

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "components" in data
        assert "youtube_connectivity" in data["components"]

    @patch("app.api.health._check_ytdlp")
    @patch("app.api.health._check_ffmpeg")
    @patch("app.api.health._check_nodejs")
    @patch("app.api.health._check_storage")
    @patch("app.api.health._check_cookies")
    def test_health_component_unhealthy(
        self,
        mock_cookies: MagicMock,
        mock_storage: MagicMock,
        mock_nodejs: MagicMock,
        mock_ffmpeg: MagicMock,
        mock_ytdlp: MagicMock,
        app: FastAPI,
    ) -> None:
        """Test health endpoint when a component is unhealthy."""
        from app.api.schemas import ComponentHealth

        mock_ytdlp.return_value = ComponentHealth(
            status="unhealthy", details={"error": "yt-dlp not found"}
        )
        mock_ffmpeg.return_value = ComponentHealth(status="healthy", version="6.0")
        mock_nodejs.return_value = ComponentHealth(status="healthy", version="v20.0.0")
        mock_storage.return_value = ComponentHealth(status="healthy")
        mock_cookies.return_value = ComponentHealth(status="healthy")

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"

    @patch("app.api.health._check_ytdlp")
    @patch("app.api.health._check_storage")
    def test_readiness_ready(
        self, mock_storage: MagicMock, mock_ytdlp: MagicMock, app: FastAPI
    ) -> None:
        """Test readiness endpoint when ready."""
        from app.api.schemas import ComponentHealth

        mock_ytdlp.return_value = ComponentHealth(status="healthy", version="2024.01.01")
        mock_storage.return_value = ComponentHealth(status="healthy")

        client = TestClient(app)
        response = client.get("/readiness")

        assert response.status_code == 200
        data = response.json()
        assert data["ready"] is True

    @patch("app.api.health._check_ytdlp")
    @patch("app.api.health._check_storage")
    def test_readiness_not_ready(
        self, mock_storage: MagicMock, mock_ytdlp: MagicMock, app: FastAPI
    ) -> None:
        """Test readiness endpoint when not ready."""
        from app.api.schemas import ComponentHealth

        mock_ytdlp.return_value = ComponentHealth(
            status="unhealthy", details={"error": "not found"}
        )
        mock_storage.return_value = ComponentHealth(status="healthy")

        client = TestClient(app)
        response = client.get("/readiness")

        assert response.status_code == 503
        data = response.json()
        assert data["ready"] is False


# ============================================================================
# Video Info Endpoint Tests
# ============================================================================


class TestVideoInfoEndpoint:
    """Tests for video info endpoint."""

    def test_info_success(
        self,
        app: FastAPI,
        mock_provider_manager: MagicMock,
        sample_video_info: dict,
    ) -> None:
        """Test successful video info retrieval."""
        mock_provider = MagicMock()
        mock_provider.get_info = AsyncMock(return_value=sample_video_info)
        mock_provider_manager.get_provider_for_url.return_value = mock_provider

        # Override dependency
        app.dependency_overrides[video.get_provider_manager] = lambda: mock_provider_manager

        client = TestClient(app)
        response = client.get(
            "/api/v1/info", params={"url": "https://www.youtube.com/watch?v=abc123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["video_id"] == "abc123"
        assert data["title"] == "Test Video"

    def test_info_invalid_url(self, app: FastAPI, mock_provider_manager: MagicMock) -> None:
        """Test info endpoint with invalid URL."""
        app.dependency_overrides[video.get_provider_manager] = lambda: mock_provider_manager

        client = TestClient(app)
        response = client.get("/api/v1/info", params={"url": "invalid-url"})

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error_code"] == "INVALID_URL"

    def test_info_video_unavailable(self, app: FastAPI, mock_provider_manager: MagicMock) -> None:
        """Test info endpoint when video unavailable."""
        mock_provider = MagicMock()
        mock_provider.get_info = AsyncMock(side_effect=VideoUnavailableError("Video not found"))
        mock_provider_manager.get_provider_for_url.return_value = mock_provider

        app.dependency_overrides[video.get_provider_manager] = lambda: mock_provider_manager

        client = TestClient(app)
        response = client.get(
            "/api/v1/info", params={"url": "https://www.youtube.com/watch?v=notfound"}
        )

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error_code"] == "VIDEO_UNAVAILABLE"

    def test_info_provider_error(self, app: FastAPI, mock_provider_manager: MagicMock) -> None:
        """Test info endpoint when provider error occurs."""
        mock_provider = MagicMock()
        mock_provider.get_info = AsyncMock(side_effect=ProviderError("Provider failed"))
        mock_provider_manager.get_provider_for_url.return_value = mock_provider

        app.dependency_overrides[video.get_provider_manager] = lambda: mock_provider_manager

        client = TestClient(app)
        response = client.get(
            "/api/v1/info", params={"url": "https://www.youtube.com/watch?v=abc123"}
        )

        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["error_code"] == "PROVIDER_ERROR"


# ============================================================================
# Formats Endpoint Tests
# ============================================================================


class TestFormatsEndpoint:
    """Tests for formats endpoint."""

    def test_formats_success(
        self,
        app: FastAPI,
        mock_provider_manager: MagicMock,
    ) -> None:
        """Test successful formats retrieval."""
        mock_provider = MagicMock()
        mock_provider.list_formats = AsyncMock(
            return_value=[
                VideoFormat(
                    format_id="22",
                    ext="mp4",
                    resolution="720p",
                    audio_bitrate=128,
                    video_codec="h264",
                    audio_codec="aac",
                    filesize=10000000,
                    format_type="video+audio",
                ),
                VideoFormat(
                    format_id="140",
                    ext="m4a",
                    resolution=None,
                    audio_bitrate=128,
                    video_codec=None,
                    audio_codec="aac",
                    filesize=1000000,
                    format_type="audio-only",
                ),
            ]
        )
        mock_provider_manager.get_provider_for_url.return_value = mock_provider

        app.dependency_overrides[video.get_provider_manager] = lambda: mock_provider_manager

        client = TestClient(app)
        response = client.get(
            "/api/v1/formats", params={"url": "https://www.youtube.com/watch?v=abc123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["formats"]) == 2
        assert len(data["video_audio"]) == 1
        assert len(data["audio_only"]) == 1


# ============================================================================
# Download Endpoint Tests
# ============================================================================


class TestDownloadEndpoint:
    """Tests for download endpoint."""

    def test_download_async_success(
        self,
        app: FastAPI,
        mock_provider_manager: MagicMock,
        mock_job_service: MagicMock,
        mock_download_queue: MagicMock,
        mock_download_worker: MagicMock,
        sample_job: Job,
    ) -> None:
        """Test async download job creation."""
        mock_job_service.create_job.return_value = sample_job
        mock_provider_manager.get_provider_for_url.return_value = MagicMock()

        app.dependency_overrides[download.get_provider_manager] = lambda: mock_provider_manager
        app.dependency_overrides[download.get_job_service] = lambda: mock_job_service
        app.dependency_overrides[download.get_download_queue] = lambda: mock_download_queue
        app.dependency_overrides[download.get_download_worker] = lambda: mock_download_worker

        client = TestClient(app)
        response = client.post(
            "/api/v1/download",
            json={"url": "https://www.youtube.com/watch?v=abc123", "async": True},
        )

        assert response.status_code == 202  # Accepted for async job creation
        data = response.json()
        assert data["job_id"] == "job-123"
        assert data["status"] == "pending"
        assert data["queue_position"] == 1

    def test_download_invalid_url(
        self,
        app: FastAPI,
        mock_provider_manager: MagicMock,
        mock_job_service: MagicMock,
        mock_download_queue: MagicMock,
        mock_download_worker: MagicMock,
    ) -> None:
        """Test download with invalid URL."""
        app.dependency_overrides[download.get_provider_manager] = lambda: mock_provider_manager
        app.dependency_overrides[download.get_job_service] = lambda: mock_job_service
        app.dependency_overrides[download.get_download_queue] = lambda: mock_download_queue
        app.dependency_overrides[download.get_download_worker] = lambda: mock_download_worker

        client = TestClient(app)
        response = client.post(
            "/api/v1/download",
            json={"url": "invalid-url", "async": True},
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error_code"] == "INVALID_URL"

    def test_download_queue_full(
        self,
        app: FastAPI,
        mock_provider_manager: MagicMock,
        mock_job_service: MagicMock,
        mock_download_queue: MagicMock,
        mock_download_worker: MagicMock,
        sample_job: Job,
    ) -> None:
        """Test download when queue is full."""
        mock_job_service.create_job.return_value = sample_job
        mock_provider_manager.get_provider_for_url.return_value = MagicMock()
        mock_download_queue.enqueue = AsyncMock(side_effect=ValueError("Queue is full"))

        app.dependency_overrides[download.get_provider_manager] = lambda: mock_provider_manager
        app.dependency_overrides[download.get_job_service] = lambda: mock_job_service
        app.dependency_overrides[download.get_download_queue] = lambda: mock_download_queue
        app.dependency_overrides[download.get_download_worker] = lambda: mock_download_worker

        client = TestClient(app)
        response = client.post(
            "/api/v1/download",
            json={"url": "https://www.youtube.com/watch?v=abc123", "async": True},
        )

        assert response.status_code == 503
        data = response.json()
        assert data["detail"]["error_code"] == "QUEUE_FULL"

    def test_download_sync_success(
        self,
        app: FastAPI,
        mock_provider_manager: MagicMock,
        mock_job_service: MagicMock,
        mock_download_queue: MagicMock,
        mock_download_worker: MagicMock,
        sample_job: Job,
    ) -> None:
        """Test successful synchronous download."""
        from datetime import datetime, timezone

        # Create completed job
        completed_job = Job(
            job_id="job-123",
            url="https://www.youtube.com/watch?v=abc123",
            status=JobStatus.COMPLETED,
            params={},
            progress=100,
            retry_count=0,
            max_retries=3,
            error_message=None,
            file_path="/app/downloads/video.mp4",
            file_size=10000000,
            duration=120.5,
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            queue_position=None,
        )

        mock_job_service.create_job.return_value = sample_job
        mock_job_service.get_job.return_value = completed_job
        mock_provider_manager.get_provider_for_url.return_value = MagicMock()

        app.dependency_overrides[download.get_provider_manager] = lambda: mock_provider_manager
        app.dependency_overrides[download.get_job_service] = lambda: mock_job_service
        app.dependency_overrides[download.get_download_queue] = lambda: mock_download_queue
        app.dependency_overrides[download.get_download_worker] = lambda: mock_download_worker

        client = TestClient(app)
        response = client.post(
            "/api/v1/download",
            json={"url": "https://www.youtube.com/watch?v=abc123", "async": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["file_path"] == "/app/downloads/video.mp4"
        assert data["file_size"] == 10000000
        assert data["duration"] == 120.5

    def test_download_sync_failed(
        self,
        app: FastAPI,
        mock_provider_manager: MagicMock,
        mock_job_service: MagicMock,
        mock_download_queue: MagicMock,
        mock_download_worker: MagicMock,
        sample_job: Job,
    ) -> None:
        """Test failed synchronous download."""
        from datetime import datetime, timezone

        # Create failed job
        failed_job = Job(
            job_id="job-123",
            url="https://www.youtube.com/watch?v=abc123",
            status=JobStatus.FAILED,
            params={},
            progress=0,
            retry_count=3,
            max_retries=3,
            error_message="Video unavailable",
            file_path=None,
            file_size=None,
            duration=None,
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            queue_position=None,
        )

        mock_job_service.create_job.return_value = sample_job
        mock_job_service.get_job.return_value = failed_job
        mock_provider_manager.get_provider_for_url.return_value = MagicMock()

        app.dependency_overrides[download.get_provider_manager] = lambda: mock_provider_manager
        app.dependency_overrides[download.get_job_service] = lambda: mock_job_service
        app.dependency_overrides[download.get_download_queue] = lambda: mock_download_queue
        app.dependency_overrides[download.get_download_worker] = lambda: mock_download_worker

        client = TestClient(app)
        response = client.post(
            "/api/v1/download",
            json={"url": "https://www.youtube.com/watch?v=abc123", "async": False},
        )

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error_code"] == "VIDEO_UNAVAILABLE"


# ============================================================================
# Jobs Endpoint Tests
# ============================================================================


class TestJobsEndpoint:
    """Tests for job status endpoint."""

    def test_job_status_success(
        self,
        app: FastAPI,
        mock_job_service: MagicMock,
        mock_download_queue: MagicMock,
        sample_job: Job,
    ) -> None:
        """Test successful job status retrieval."""
        mock_job_service.get_job_or_raise.return_value = sample_job

        app.dependency_overrides[jobs.get_job_service] = lambda: mock_job_service
        app.dependency_overrides[jobs.get_download_queue] = lambda: mock_download_queue

        client = TestClient(app)
        response = client.get("/api/v1/jobs/job-123")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "job-123"
        assert data["status"] == "pending"

    def test_job_status_not_found(
        self,
        app: FastAPI,
        mock_job_service: MagicMock,
        mock_download_queue: MagicMock,
    ) -> None:
        """Test job status when job not found."""
        from app.services.job_service import JobNotFoundError

        mock_job_service.get_job_or_raise.side_effect = JobNotFoundError("not-found")

        app.dependency_overrides[jobs.get_job_service] = lambda: mock_job_service
        app.dependency_overrides[jobs.get_download_queue] = lambda: mock_download_queue

        client = TestClient(app)
        response = client.get("/api/v1/jobs/not-found")

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error_code"] == "JOB_NOT_FOUND"

    def test_job_status_completed(
        self,
        app: FastAPI,
        mock_job_service: MagicMock,
        mock_download_queue: MagicMock,
        sample_job: Job,
    ) -> None:
        """Test job status for completed job."""
        from datetime import datetime, timezone

        sample_job.status = JobStatus.COMPLETED
        sample_job.progress = 100
        sample_job.file_path = "/app/downloads/video.mp4"
        sample_job.file_size = 10000000
        sample_job.duration = 120.5
        sample_job.completed_at = datetime.now(timezone.utc)
        mock_job_service.get_job_or_raise.return_value = sample_job

        app.dependency_overrides[jobs.get_job_service] = lambda: mock_job_service
        app.dependency_overrides[jobs.get_download_queue] = lambda: mock_download_queue

        client = TestClient(app)
        response = client.get("/api/v1/jobs/job-123")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["progress"] == 100
        assert data["file_path"] == "/app/downloads/video.mp4"


# ============================================================================
# Schema Validation Tests
# ============================================================================


class TestSchemaValidation:
    """Tests for request schema validation."""

    def test_download_request_audio_format_valid(
        self,
        app: FastAPI,
        mock_provider_manager: MagicMock,
        mock_job_service: MagicMock,
        mock_download_queue: MagicMock,
        mock_download_worker: MagicMock,
        sample_job: Job,
    ) -> None:
        """Test download request with valid audio format."""
        mock_job_service.create_job.return_value = sample_job
        mock_provider_manager.get_provider_for_url.return_value = MagicMock()

        app.dependency_overrides[download.get_provider_manager] = lambda: mock_provider_manager
        app.dependency_overrides[download.get_job_service] = lambda: mock_job_service
        app.dependency_overrides[download.get_download_queue] = lambda: mock_download_queue
        app.dependency_overrides[download.get_download_worker] = lambda: mock_download_worker

        client = TestClient(app)
        response = client.post(
            "/api/v1/download",
            json={
                "url": "https://www.youtube.com/watch?v=abc123",
                "extract_audio": True,
                "audio_format": "mp3",
            },
        )

        assert response.status_code == 202  # Accepted for async job creation

    def test_download_request_audio_format_invalid(
        self,
        app: FastAPI,
        mock_provider_manager: MagicMock,
        mock_job_service: MagicMock,
        mock_download_queue: MagicMock,
        mock_download_worker: MagicMock,
    ) -> None:
        """Test download request with invalid audio format."""
        app.dependency_overrides[download.get_provider_manager] = lambda: mock_provider_manager
        app.dependency_overrides[download.get_job_service] = lambda: mock_job_service
        app.dependency_overrides[download.get_download_queue] = lambda: mock_download_queue
        app.dependency_overrides[download.get_download_worker] = lambda: mock_download_worker

        client = TestClient(app)
        response = client.post(
            "/api/v1/download",
            json={
                "url": "https://www.youtube.com/watch?v=abc123",
                "extract_audio": True,
                "audio_format": "invalid",
            },
        )

        assert response.status_code == 422  # Validation error


# ============================================================================
# Download Endpoint Error Path Tests (validation and sync mode)
# ============================================================================


def _override_download_deps(
    app: FastAPI,
    provider_manager: MagicMock,
    job_service: MagicMock,
    download_queue: MagicMock,
    download_worker: MagicMock,
) -> None:
    """Wire mocked download dependencies into the test app."""
    app.dependency_overrides[download.get_provider_manager] = lambda: provider_manager
    app.dependency_overrides[download.get_job_service] = lambda: job_service
    app.dependency_overrides[download.get_download_queue] = lambda: download_queue
    app.dependency_overrides[download.get_download_worker] = lambda: download_worker


def _make_job(status: JobStatus, error_message: str | None = None) -> Job:
    """Build a job in the given terminal state."""
    from datetime import datetime, timezone

    return Job(
        job_id="job-123",
        url="https://www.youtube.com/watch?v=abc123",
        status=status,
        params={},
        progress=100,
        retry_count=0,
        max_retries=3,
        error_message=error_message,
        file_path="/app/downloads/video.mp4" if status == JobStatus.COMPLETED else None,
        file_size=10000000 if status == JobStatus.COMPLETED else None,
        duration=12.5 if status == JobStatus.COMPLETED else None,
        created_at=datetime.now(timezone.utc),
        started_at=None,
        completed_at=None,
        queue_position=None,
    )


class TestDownloadValidationErrors:
    """Request validation branches of the download endpoint."""

    def test_invalid_format_id(
        self,
        app: FastAPI,
        mock_provider_manager: MagicMock,
        mock_job_service: MagicMock,
        mock_download_queue: MagicMock,
        mock_download_worker: MagicMock,
    ) -> None:
        """Malformed format_id returns 400 INVALID_FORMAT."""
        _override_download_deps(
            app, mock_provider_manager, mock_job_service, mock_download_queue, mock_download_worker
        )

        client = TestClient(app)
        response = client.post(
            "/api/v1/download",
            json={
                "url": "https://www.youtube.com/watch?v=abc123",
                "format_id": "22; rm -rf /",
                "async": True,
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"]["error_code"] == "INVALID_FORMAT"

    def test_invalid_output_template(
        self,
        app: FastAPI,
        mock_provider_manager: MagicMock,
        mock_job_service: MagicMock,
        mock_download_queue: MagicMock,
        mock_download_worker: MagicMock,
    ) -> None:
        """Path traversal in output_template returns 400 INVALID_TEMPLATE."""
        _override_download_deps(
            app, mock_provider_manager, mock_job_service, mock_download_queue, mock_download_worker
        )

        client = TestClient(app)
        response = client.post(
            "/api/v1/download",
            json={
                "url": "https://www.youtube.com/watch?v=abc123",
                "output_template": "../../etc/passwd",
                "async": True,
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"]["error_code"] == "INVALID_TEMPLATE"

    def test_no_provider_for_url(
        self,
        app: FastAPI,
        mock_provider_manager: MagicMock,
        mock_job_service: MagicMock,
        mock_download_queue: MagicMock,
        mock_download_worker: MagicMock,
    ) -> None:
        """URL without a provider returns 400 INVALID_URL."""
        from app.providers.exceptions import InvalidURLError

        mock_provider_manager.get_provider_for_url.side_effect = InvalidURLError(
            "No provider available"
        )
        _override_download_deps(
            app, mock_provider_manager, mock_job_service, mock_download_queue, mock_download_worker
        )

        client = TestClient(app)
        response = client.post(
            "/api/v1/download",
            json={"url": "https://www.youtube.com/watch?v=abc123", "async": True},
        )

        assert response.status_code == 400
        assert response.json()["detail"]["error_code"] == "INVALID_URL"


class TestSyncDownloadErrorPaths:
    """Synchronous download branch coverage."""

    def _post_sync(self, app: FastAPI) -> "TestClient.post":
        client = TestClient(app)
        return client.post(
            "/api/v1/download",
            json={"url": "https://www.youtube.com/watch?v=abc123", "async": False},
        )

    def test_no_slots_available(
        self,
        app: FastAPI,
        mock_provider_manager: MagicMock,
        mock_job_service: MagicMock,
        mock_download_queue: MagicMock,
        mock_download_worker: MagicMock,
        sample_job: Job,
    ) -> None:
        """Saturated slots return 503 NO_SLOTS_AVAILABLE."""
        mock_job_service.create_job.return_value = sample_job
        mock_provider_manager.get_provider_for_url.return_value = MagicMock()
        mock_download_queue.acquire_slot_for_sync = AsyncMock(return_value=False)
        _override_download_deps(
            app, mock_provider_manager, mock_job_service, mock_download_queue, mock_download_worker
        )

        response = self._post_sync(app)

        assert response.status_code == 503
        assert response.json()["detail"]["error_code"] == "NO_SLOTS_AVAILABLE"
        mock_job_service.fail_job.assert_called_once()

    def test_job_missing_after_processing(
        self,
        app: FastAPI,
        mock_provider_manager: MagicMock,
        mock_job_service: MagicMock,
        mock_download_queue: MagicMock,
        mock_download_worker: MagicMock,
        sample_job: Job,
    ) -> None:
        """Job vanished after processing returns 500 INTERNAL_ERROR."""
        mock_job_service.create_job.return_value = sample_job
        mock_job_service.get_job.return_value = None
        mock_provider_manager.get_provider_for_url.return_value = MagicMock()
        _override_download_deps(
            app, mock_provider_manager, mock_job_service, mock_download_queue, mock_download_worker
        )

        response = self._post_sync(app)

        assert response.status_code == 500
        assert response.json()["detail"]["error_code"] == "INTERNAL_ERROR"

    @pytest.mark.parametrize(
        "error_message,expected_status,expected_code",
        [
            ("Video is unavailable in your region", 404, "VIDEO_UNAVAILABLE"),
            ("Requested format not found", 400, "FORMAT_NOT_FOUND"),
            ("Network connection reset", 500, "DOWNLOAD_FAILED"),
        ],
    )
    def test_failed_job_error_mapping(
        self,
        app: FastAPI,
        mock_provider_manager: MagicMock,
        mock_job_service: MagicMock,
        mock_download_queue: MagicMock,
        mock_download_worker: MagicMock,
        sample_job: Job,
        error_message: str,
        expected_status: int,
        expected_code: str,
    ) -> None:
        """Failed jobs map error messages to proper HTTP codes."""
        mock_job_service.create_job.return_value = sample_job
        mock_job_service.get_job.return_value = _make_job(JobStatus.FAILED, error_message)
        mock_provider_manager.get_provider_for_url.return_value = MagicMock()
        _override_download_deps(
            app, mock_provider_manager, mock_job_service, mock_download_queue, mock_download_worker
        )

        response = self._post_sync(app)

        assert response.status_code == expected_status
        assert response.json()["detail"]["error_code"] == expected_code

    def test_unexpected_job_status(
        self,
        app: FastAPI,
        mock_provider_manager: MagicMock,
        mock_job_service: MagicMock,
        mock_download_queue: MagicMock,
        mock_download_worker: MagicMock,
        sample_job: Job,
    ) -> None:
        """A non-terminal status after sync processing returns 500."""
        mock_job_service.create_job.return_value = sample_job
        mock_job_service.get_job.return_value = _make_job(JobStatus.PENDING)
        mock_provider_manager.get_provider_for_url.return_value = MagicMock()
        _override_download_deps(
            app, mock_provider_manager, mock_job_service, mock_download_queue, mock_download_worker
        )

        response = self._post_sync(app)

        assert response.status_code == 500
        assert response.json()["detail"]["error_code"] == "INTERNAL_ERROR"

    def test_worker_exception_maps_to_download_failed(
        self,
        app: FastAPI,
        mock_provider_manager: MagicMock,
        mock_job_service: MagicMock,
        mock_download_queue: MagicMock,
        mock_download_worker: MagicMock,
        sample_job: Job,
    ) -> None:
        """Unexpected worker exceptions return 500 DOWNLOAD_FAILED."""
        mock_job_service.create_job.return_value = sample_job
        mock_provider_manager.get_provider_for_url.return_value = MagicMock()
        mock_download_worker.process_single_job = AsyncMock(side_effect=RuntimeError("boom"))
        _override_download_deps(
            app, mock_provider_manager, mock_job_service, mock_download_queue, mock_download_worker
        )

        response = self._post_sync(app)

        assert response.status_code == 500
        assert response.json()["detail"]["error_code"] == "DOWNLOAD_FAILED"


# ============================================================================
# Video/Formats Endpoint Error Path Tests
# ============================================================================


class TestVideoInfoErrorPaths:
    """Error branches of GET /api/v1/info."""

    def test_no_provider_for_url(self, app: FastAPI, mock_provider_manager: MagicMock) -> None:
        """Provider selection failure returns 400 INVALID_URL."""
        from app.providers.exceptions import InvalidURLError

        mock_provider_manager.get_provider_for_url.side_effect = InvalidURLError("No provider")
        app.dependency_overrides[video.get_provider_manager] = lambda: mock_provider_manager

        client = TestClient(app)
        response = client.get(
            "/api/v1/info", params={"url": "https://www.youtube.com/watch?v=abc123"}
        )

        assert response.status_code == 400
        assert response.json()["detail"]["error_code"] == "INVALID_URL"

    def test_unexpected_error(self, app: FastAPI, mock_provider_manager: MagicMock) -> None:
        """Generic provider exceptions return 500 INTERNAL_ERROR."""
        mock_provider = MagicMock()
        mock_provider.get_info = AsyncMock(side_effect=RuntimeError("boom"))
        mock_provider_manager.get_provider_for_url.return_value = mock_provider
        app.dependency_overrides[video.get_provider_manager] = lambda: mock_provider_manager

        client = TestClient(app)
        response = client.get(
            "/api/v1/info", params={"url": "https://www.youtube.com/watch?v=abc123"}
        )

        assert response.status_code == 500
        assert response.json()["detail"]["error_code"] == "INTERNAL_ERROR"


class TestFormatsErrorPaths:
    """Error branches of GET /api/v1/formats."""

    def test_invalid_url_param(self, app: FastAPI, mock_provider_manager: MagicMock) -> None:
        """Malformed URL returns 400 INVALID_URL before provider lookup."""
        app.dependency_overrides[video.get_provider_manager] = lambda: mock_provider_manager

        client = TestClient(app)
        response = client.get("/api/v1/formats", params={"url": "not-a-url"})

        assert response.status_code == 400
        assert response.json()["detail"]["error_code"] == "INVALID_URL"

    def test_no_provider_for_url(self, app: FastAPI, mock_provider_manager: MagicMock) -> None:
        """Provider selection failure returns 400 INVALID_URL."""
        from app.providers.exceptions import InvalidURLError

        mock_provider_manager.get_provider_for_url.side_effect = InvalidURLError("No provider")
        app.dependency_overrides[video.get_provider_manager] = lambda: mock_provider_manager

        client = TestClient(app)
        response = client.get(
            "/api/v1/formats", params={"url": "https://www.youtube.com/watch?v=abc123"}
        )

        assert response.status_code == 400
        assert response.json()["detail"]["error_code"] == "INVALID_URL"

    def test_video_unavailable(self, app: FastAPI, mock_provider_manager: MagicMock) -> None:
        """Unavailable video returns 404 VIDEO_UNAVAILABLE."""
        mock_provider = MagicMock()
        mock_provider.list_formats = AsyncMock(side_effect=VideoUnavailableError("gone"))
        mock_provider_manager.get_provider_for_url.return_value = mock_provider
        app.dependency_overrides[video.get_provider_manager] = lambda: mock_provider_manager

        client = TestClient(app)
        response = client.get(
            "/api/v1/formats", params={"url": "https://www.youtube.com/watch?v=abc123"}
        )

        assert response.status_code == 404
        assert response.json()["detail"]["error_code"] == "VIDEO_UNAVAILABLE"

    def test_provider_error(self, app: FastAPI, mock_provider_manager: MagicMock) -> None:
        """Provider errors return 500 PROVIDER_ERROR."""
        mock_provider = MagicMock()
        mock_provider.list_formats = AsyncMock(side_effect=ProviderError("failed"))
        mock_provider_manager.get_provider_for_url.return_value = mock_provider
        app.dependency_overrides[video.get_provider_manager] = lambda: mock_provider_manager

        client = TestClient(app)
        response = client.get(
            "/api/v1/formats", params={"url": "https://www.youtube.com/watch?v=abc123"}
        )

        assert response.status_code == 500
        assert response.json()["detail"]["error_code"] == "PROVIDER_ERROR"

    def test_unexpected_error(self, app: FastAPI, mock_provider_manager: MagicMock) -> None:
        """Generic exceptions return 500 INTERNAL_ERROR."""
        mock_provider = MagicMock()
        mock_provider.list_formats = AsyncMock(side_effect=RuntimeError("boom"))
        mock_provider_manager.get_provider_for_url.return_value = mock_provider
        app.dependency_overrides[video.get_provider_manager] = lambda: mock_provider_manager

        client = TestClient(app)
        response = client.get(
            "/api/v1/formats", params={"url": "https://www.youtube.com/watch?v=abc123"}
        )

        assert response.status_code == 500
        assert response.json()["detail"]["error_code"] == "INTERNAL_ERROR"


# ============================================================================
# Transcript Endpoint Tests
# ============================================================================


class TestTranscriptEndpoint:
    """Tests for GET /api/v1/transcript."""

    @staticmethod
    def _demo_transcript() -> dict:
        from app.utils.transcript import TranscriptSegment

        return {
            "video_id": "dQw4w9WgXcQ",
            "lang": "en",
            "source": "manual",
            "segments": [
                TranscriptSegment(start=0.0, end=2.5, text="We're no strangers to love"),
                TranscriptSegment(start=2.5, end=5.0, text="You know the rules and so do I"),
            ],
            "raw_vtt": "WEBVTT\n\n00:00:00.000 --> 00:00:02.500\nWe're no strangers to love\n",
        }

    def _client(self, app: FastAPI, mock_provider_manager: MagicMock) -> TestClient:
        app.dependency_overrides[transcript.get_provider_manager] = lambda: mock_provider_manager
        return TestClient(app)

    def test_transcript_json(self, app: FastAPI, mock_provider_manager: MagicMock) -> None:
        """Default JSON format returns segments and flattened text."""
        mock_provider = MagicMock()
        mock_provider.get_transcript = AsyncMock(return_value=self._demo_transcript())
        mock_provider_manager.get_provider_for_url.return_value = mock_provider

        client = self._client(app, mock_provider_manager)
        response = client.get(
            "/api/v1/transcript",
            params={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["video_id"] == "dQw4w9WgXcQ"
        assert data["source"] == "manual"
        assert data["segment_count"] == 2
        assert data["segments"][0]["text"] == "We're no strangers to love"
        assert "You know the rules" in data["text"]

    def test_transcript_text_format(self, app: FastAPI, mock_provider_manager: MagicMock) -> None:
        """fmt=text returns plain text with one segment per line."""
        mock_provider = MagicMock()
        mock_provider.get_transcript = AsyncMock(return_value=self._demo_transcript())
        mock_provider_manager.get_provider_for_url.return_value = mock_provider

        client = self._client(app, mock_provider_manager)
        response = client.get(
            "/api/v1/transcript",
            params={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "fmt": "text"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        assert response.text == "We're no strangers to love\nYou know the rules and so do I"

    def test_transcript_srt_format(self, app: FastAPI, mock_provider_manager: MagicMock) -> None:
        """fmt=srt returns SubRip cues."""
        mock_provider = MagicMock()
        mock_provider.get_transcript = AsyncMock(return_value=self._demo_transcript())
        mock_provider_manager.get_provider_for_url.return_value = mock_provider

        client = self._client(app, mock_provider_manager)
        response = client.get(
            "/api/v1/transcript",
            params={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "fmt": "srt"},
        )

        assert response.status_code == 200
        assert response.text.startswith("1\n00:00:00,000 --> 00:00:02,500")

    def test_transcript_vtt_format(self, app: FastAPI, mock_provider_manager: MagicMock) -> None:
        """fmt=vtt returns the raw VTT file."""
        mock_provider = MagicMock()
        mock_provider.get_transcript = AsyncMock(return_value=self._demo_transcript())
        mock_provider_manager.get_provider_for_url.return_value = mock_provider

        client = self._client(app, mock_provider_manager)
        response = client.get(
            "/api/v1/transcript",
            params={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "fmt": "vtt"},
        )

        assert response.status_code == 200
        assert response.text.startswith("WEBVTT")

    def test_transcript_not_found(self, app: FastAPI, mock_provider_manager: MagicMock) -> None:
        """Missing captions map to 404 TRANSCRIPT_NOT_FOUND."""
        from app.providers.exceptions import TranscriptNotFoundError

        mock_provider = MagicMock()
        mock_provider.get_transcript = AsyncMock(
            side_effect=TranscriptNotFoundError("No transcript available for language 'it'")
        )
        mock_provider_manager.get_provider_for_url.return_value = mock_provider

        client = self._client(app, mock_provider_manager)
        response = client.get(
            "/api/v1/transcript",
            params={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "lang": "it"},
        )

        assert response.status_code == 404
        assert response.json()["detail"]["error_code"] == "TRANSCRIPT_NOT_FOUND"

    def test_transcript_invalid_url(self, app: FastAPI, mock_provider_manager: MagicMock) -> None:
        """Malformed URLs return 400 before provider involvement."""
        client = self._client(app, mock_provider_manager)
        response = client.get("/api/v1/transcript", params={"url": "not-a-url"})

        assert response.status_code == 400
        assert response.json()["detail"]["error_code"] == "INVALID_URL"

    def test_transcript_invalid_lang_rejected(
        self, app: FastAPI, mock_provider_manager: MagicMock
    ) -> None:
        """Language codes outside the pattern are rejected with 422."""
        client = self._client(app, mock_provider_manager)
        response = client.get(
            "/api/v1/transcript",
            params={
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "lang": "en; rm -rf /",
            },
        )

        assert response.status_code == 422

    def test_transcript_invalid_fmt_rejected(
        self, app: FastAPI, mock_provider_manager: MagicMock
    ) -> None:
        """Unknown output formats are rejected with 422."""
        client = self._client(app, mock_provider_manager)
        response = client.get(
            "/api/v1/transcript",
            params={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "fmt": "xml"},
        )

        assert response.status_code == 422

    def test_transcript_provider_error(
        self, app: FastAPI, mock_provider_manager: MagicMock
    ) -> None:
        """Provider errors map to 500 PROVIDER_ERROR."""
        mock_provider = MagicMock()
        mock_provider.get_transcript = AsyncMock(side_effect=ProviderError("boom"))
        mock_provider_manager.get_provider_for_url.return_value = mock_provider

        client = self._client(app, mock_provider_manager)
        response = client.get(
            "/api/v1/transcript",
            params={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )

        assert response.status_code == 500
        assert response.json()["detail"]["error_code"] == "PROVIDER_ERROR"

    def test_transcript_video_unavailable(
        self, app: FastAPI, mock_provider_manager: MagicMock
    ) -> None:
        """Unavailable videos map to 404 VIDEO_UNAVAILABLE."""
        mock_provider = MagicMock()
        mock_provider.get_transcript = AsyncMock(side_effect=VideoUnavailableError("gone"))
        mock_provider_manager.get_provider_for_url.return_value = mock_provider

        client = self._client(app, mock_provider_manager)
        response = client.get(
            "/api/v1/transcript",
            params={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )

        assert response.status_code == 404
        assert response.json()["detail"]["error_code"] == "VIDEO_UNAVAILABLE"

    def test_transcript_unexpected_error(
        self, app: FastAPI, mock_provider_manager: MagicMock
    ) -> None:
        """Generic exceptions map to 500 INTERNAL_ERROR."""
        mock_provider = MagicMock()
        mock_provider.get_transcript = AsyncMock(side_effect=RuntimeError("boom"))
        mock_provider_manager.get_provider_for_url.return_value = mock_provider

        client = self._client(app, mock_provider_manager)
        response = client.get(
            "/api/v1/transcript",
            params={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )

        assert response.status_code == 500
        assert response.json()["detail"]["error_code"] == "INTERNAL_ERROR"

    def test_transcript_no_provider(self, app: FastAPI, mock_provider_manager: MagicMock) -> None:
        """Provider selection failure maps to 400 INVALID_URL."""
        from app.providers.exceptions import InvalidURLError

        mock_provider_manager.get_provider_for_url.side_effect = InvalidURLError("No provider")

        client = self._client(app, mock_provider_manager)
        response = client.get(
            "/api/v1/transcript",
            params={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )

        assert response.status_code == 400
        assert response.json()["detail"]["error_code"] == "INVALID_URL"
