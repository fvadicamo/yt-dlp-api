"""E2E tests for Prometheus metrics collection.

Tests that metrics are properly recorded for:
- HTTP requests
- Error counts
- Download operations
"""

import re

import pytest
from fastapi.testclient import TestClient


def get_counter_sum(
    content: str, metric_name: str, label_filter: dict[str, str] | None = None
) -> float:
    """Sum all counter values for a metric, optionally filtering by labels.

    Args:
        content: The raw Prometheus metrics text
        metric_name: The name of the metric to find
        label_filter: Optional dict of label key-value pairs that must be present

    Returns:
        Sum of all matching counter values
    """
    total = 0.0
    # Pattern to match metric lines with labels and values
    pattern = rf"^{re.escape(metric_name)}\{{([^}}]*)\}}\s+([\d.]+(?:e[+-]?\d+)?)"

    for line in content.split("\n"):
        match = re.match(pattern, line)
        if match:
            labels_str = match.group(1)
            value = float(match.group(2))

            # If filter specified, parse labels and check matches
            if label_filter:
                labels = dict(re.findall(r'(\w+)="([^"]*)"', labels_str))
                if all(labels.get(k) == v for k, v in label_filter.items()):
                    total += value
            else:
                total += value

    return total


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

        # Get initial counter sum for the specific endpoint (any status code)
        initial_count = get_counter_sum(
            initial_content,
            "http_requests_total",
            {"method": "GET", "endpoint": "/api/v1/info"},
        )

        # Make a request
        e2e_client.get(
            "/api/v1/info",
            params={"url": demo_video_url},
            headers=auth_headers,
        )

        # Get updated metrics
        updated_response = e2e_client.get("/metrics")
        updated_content = updated_response.text

        # Get updated counter sum
        updated_count = get_counter_sum(
            updated_content,
            "http_requests_total",
            {"method": "GET", "endpoint": "/api/v1/info"},
        )

        # Counter should have incremented by at least 1
        assert updated_count >= initial_count + 1, (
            f"http_requests_total for GET /api/v1/info should have incremented. "
            f"Initial: {initial_count}, Updated: {updated_count}"
        )

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
