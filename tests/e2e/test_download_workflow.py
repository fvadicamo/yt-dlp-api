"""E2E tests for complete download workflow.

Tests the full request flow:
1. GET /api/v1/info - Get video metadata
2. GET /api/v1/formats - List available formats
3. POST /api/v1/download - Start async download
4. GET /api/v1/jobs/{id} - Poll job status
"""

import time

import pytest
from fastapi.testclient import TestClient


@pytest.mark.e2e
class TestVideoInfoWorkflow:
    """E2E tests for video info retrieval."""

    def test_get_video_info(
        self, e2e_client: TestClient, auth_headers: dict, demo_video_url: str
    ) -> None:
        """Test retrieving video metadata."""
        response = e2e_client.get(
            "/api/v1/info",
            params={"url": demo_video_url},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["video_id"] == "dQw4w9WgXcQ"
        assert "Rick Astley" in data["title"]
        assert data["duration"] > 0
        assert data["author"] == "Rick Astley"

    def test_get_video_info_with_formats(
        self, e2e_client: TestClient, auth_headers: dict, demo_video_url: str
    ) -> None:
        """Test retrieving video info with formats included."""
        response = e2e_client.get(
            "/api/v1/info",
            params={"url": demo_video_url, "include_formats": True},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "formats" in data
        assert len(data["formats"]) > 0

    def test_get_short_video_info(
        self, e2e_client: TestClient, auth_headers: dict, short_video_url: str
    ) -> None:
        """Test retrieving short video metadata (Me at the zoo)."""
        response = e2e_client.get(
            "/api/v1/info",
            params={"url": short_video_url},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["video_id"] == "jNQXAC9IVRw"
        assert data["title"] == "Me at the zoo"
        assert data["duration"] == 19  # 19 seconds


@pytest.mark.e2e
class TestFormatsWorkflow:
    """E2E tests for format listing."""

    def test_list_formats(
        self, e2e_client: TestClient, auth_headers: dict, demo_video_url: str
    ) -> None:
        """Test listing available formats for a video."""
        response = e2e_client.get(
            "/api/v1/formats",
            params={"url": demo_video_url},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "formats" in data
        assert len(data["formats"]) > 0

        # Check format structure
        fmt = data["formats"][0]
        assert "format_id" in fmt
        assert "ext" in fmt


@pytest.mark.e2e
class TestDownloadWorkflow:
    """E2E tests for async download workflow."""

    def test_async_download_complete_workflow(
        self, e2e_client: TestClient, auth_headers: dict, demo_video_url: str
    ) -> None:
        """Test complete async download workflow.

        Steps:
        1. Start async download
        2. Get job ID
        3. Poll status until complete
        4. Verify job completed successfully
        """
        # Step 1: Start async download
        response = e2e_client.post(
            "/api/v1/download",
            json={"url": demo_video_url},
            headers=auth_headers,
        )

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        job_id = data["job_id"]
        assert data["status"] == "pending"

        # Step 2: Poll job status
        max_attempts = 20
        completed = False

        for _ in range(max_attempts):
            response = e2e_client.get(
                f"/api/v1/jobs/{job_id}",
                headers=auth_headers,
            )
            assert response.status_code == 200
            job_data = response.json()

            if job_data["status"] == "completed":
                completed = True
                assert job_data["file_path"] is not None
                break
            elif job_data["status"] == "failed":
                pytest.fail(f"Job failed: {job_data.get('error_message')}")

            time.sleep(0.2)

        assert completed, "Job did not complete in time"

    def test_audio_extraction_workflow(
        self, e2e_client: TestClient, auth_headers: dict, short_video_url: str
    ) -> None:
        """Test audio-only download workflow."""
        response = e2e_client.post(
            "/api/v1/download",
            json={
                "url": short_video_url,
                "extract_audio": True,
                "audio_format": "mp3",
            },
            headers=auth_headers,
        )

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data

        # Poll for completion
        job_id = data["job_id"]
        max_attempts = 20

        for _ in range(max_attempts):
            response = e2e_client.get(
                f"/api/v1/jobs/{job_id}",
                headers=auth_headers,
            )
            job_data = response.json()

            if job_data["status"] == "completed":
                # Audio extraction should produce mp3
                assert job_data.get("file_path") is not None
                break

            time.sleep(0.2)


@pytest.mark.e2e
class TestHealthDuringOperations:
    """E2E tests for health checks during operations."""

    def test_health_check_shows_test_mode(self, e2e_client: TestClient) -> None:
        """Test that health check indicates test mode is active."""
        response = e2e_client.get("/health")

        # May be 200 or 503 depending on component health
        assert response.status_code in (200, 503)
        data = response.json()
        assert data["test_mode"] is True

    def test_liveness_during_download(
        self, e2e_client: TestClient, auth_headers: dict, demo_video_url: str
    ) -> None:
        """Test liveness probe responds during download operations."""
        # Start a download
        e2e_client.post(
            "/api/v1/download",
            json={"url": demo_video_url},
            headers=auth_headers,
        )

        # Check liveness
        response = e2e_client.get("/liveness")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"
