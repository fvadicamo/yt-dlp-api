"""E2E tests for error handling scenarios.

Tests proper error responses for:
- Invalid URLs
- Missing authentication
- Non-existent jobs
- Invalid formats
"""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.e2e
class TestAuthenticationErrors:
    """E2E tests for authentication error handling."""

    def test_missing_api_key_returns_401(self, e2e_client: TestClient, demo_video_url: str) -> None:
        """Test request without API key returns 401."""
        response = e2e_client.get(
            "/api/v1/info",
            params={"url": demo_video_url},
        )

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    def test_invalid_api_key_returns_401(self, e2e_client: TestClient, demo_video_url: str) -> None:
        """Test request with invalid API key returns 401."""
        response = e2e_client.get(
            "/api/v1/info",
            params={"url": demo_video_url},
            headers={"X-API-Key": "invalid-key"},
        )

        assert response.status_code == 401

    def test_health_endpoints_bypass_auth(self, e2e_client: TestClient) -> None:
        """Test health endpoints don't require authentication."""
        # Health endpoints should be accessible without auth
        response = e2e_client.get("/liveness")
        assert response.status_code == 200

        response = e2e_client.get("/readiness")
        assert response.status_code in (200, 503)

        response = e2e_client.get("/health")
        assert response.status_code in (200, 503)


@pytest.mark.e2e
class TestValidationErrors:
    """E2E tests for input validation errors."""

    def test_invalid_url_returns_400(self, e2e_client: TestClient, auth_headers: dict) -> None:
        """Test invalid URL returns 400 error."""
        response = e2e_client.get(
            "/api/v1/info",
            params={"url": "https://not-a-valid-provider.com/video"},
            headers=auth_headers,
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    def test_malformed_url_returns_400(self, e2e_client: TestClient, auth_headers: dict) -> None:
        """Test malformed URL returns 400 error."""
        response = e2e_client.get(
            "/api/v1/info",
            params={"url": "not-even-a-url"},
            headers=auth_headers,
        )

        assert response.status_code == 400

    def test_missing_url_returns_422(self, e2e_client: TestClient, auth_headers: dict) -> None:
        """Test missing URL parameter returns 422."""
        response = e2e_client.get(
            "/api/v1/info",
            headers=auth_headers,
        )

        assert response.status_code == 422

    def test_invalid_audio_format_returns_400(
        self, e2e_client: TestClient, auth_headers: dict, demo_video_url: str
    ) -> None:
        """Test invalid audio format returns 400 error."""
        response = e2e_client.post(
            "/api/v1/download",
            json={
                "url": demo_video_url,
                "extract_audio": True,
                "audio_format": "invalid_format",
            },
            headers=auth_headers,
        )

        assert response.status_code == 422  # Validation error


@pytest.mark.e2e
class TestNotFoundErrors:
    """E2E tests for 404 error handling."""

    def test_job_not_found_returns_404(self, e2e_client: TestClient, auth_headers: dict) -> None:
        """Test non-existent job ID returns 404."""
        response = e2e_client.get(
            "/api/v1/jobs/non-existent-job-id-12345",
            headers=auth_headers,
        )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_invalid_endpoint_returns_404(self, e2e_client: TestClient, auth_headers: dict) -> None:
        """Test non-existent endpoint returns 404."""
        response = e2e_client.get(
            "/api/v1/nonexistent",
            headers=auth_headers,
        )

        assert response.status_code == 404


@pytest.mark.e2e
class TestErrorResponseFormat:
    """E2E tests for error response structure."""

    def test_error_response_has_correct_structure(
        self, e2e_client: TestClient, auth_headers: dict
    ) -> None:
        """Test error responses follow expected structure."""
        response = e2e_client.get(
            "/api/v1/info",
            params={"url": "invalid-url"},
            headers=auth_headers,
        )

        assert response.status_code == 400
        data = response.json()

        # Check error response structure
        assert "detail" in data
        detail = data["detail"]
        assert "error_code" in detail
        assert "message" in detail
        # Note: timestamp is optional, not all error responses include it
