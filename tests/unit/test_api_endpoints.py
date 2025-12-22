"""Tests for API endpoints.

This module tests the API endpoints implementation (Task 9).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import download, health, jobs, video
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
