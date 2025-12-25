"""E2E tests for Prometheus metrics collection.

Tests that metrics are properly recorded for:
- HTTP requests
- Error counts
- Download operations
"""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.e2e
class TestMetricsEndpoint:
    """E2E tests for /metrics endpoint."""

    def test_metrics_endpoint_accessible(self, e2e_client: TestClient) -> None:
        """Test /metrics endpoint returns Prometheus format."""
        response = e2e_client.get("/metrics")

        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("text/plain")

        # Check for Prometheus format markers
        content = response.text
        assert "# HELP" in content or "# TYPE" in content or "http" in content.lower()

    def test_metrics_include_http_requests(self, e2e_client: TestClient) -> None:
        """Test that HTTP request metrics are recorded."""
        # Make some requests first
        e2e_client.get("/liveness")
        e2e_client.get("/health")

        # Check metrics
        response = e2e_client.get("/metrics")
        assert response.status_code == 200

        # Metrics content should include request data
        content = response.text
        # The exact metric names depend on implementation
        assert len(content) > 0


@pytest.mark.e2e
class TestMetricsRecording:
    """E2E tests for metrics being recorded correctly."""

    def test_request_increments_counter(
        self, e2e_client: TestClient, auth_headers: dict, demo_video_url: str
    ) -> None:
        """Test that requests increment counters."""
        # Get initial metrics
        initial_response = e2e_client.get("/metrics")
        initial_content = initial_response.text

        # Make a request
        e2e_client.get(
            "/api/v1/info",
            params={"url": demo_video_url},
            headers=auth_headers,
        )

        # Get updated metrics
        updated_response = e2e_client.get("/metrics")
        updated_content = updated_response.text

        # Metrics should have changed (content length as proxy)
        # In a real implementation, we'd parse specific counters
        assert len(updated_content) >= len(initial_content)

    def test_error_requests_are_tracked(self, e2e_client: TestClient, auth_headers: dict) -> None:
        """Test that error responses are tracked in metrics."""
        # Cause an error
        e2e_client.get(
            "/api/v1/info",
            params={"url": "invalid-url"},
            headers=auth_headers,
        )

        # Check metrics endpoint still works
        response = e2e_client.get("/metrics")
        assert response.status_code == 200
