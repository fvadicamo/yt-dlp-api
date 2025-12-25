"""Tests for admin API endpoints."""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin import router
from app.providers.exceptions import CookieError
from app.services.cookie_service import CookieService


@pytest.fixture
def mock_cookie_service():
    """Create mock cookie service."""
    service = AsyncMock(spec=CookieService)
    return service


@pytest.fixture
def app(mock_cookie_service):
    """Create FastAPI test app."""
    app = FastAPI()
    app.include_router(router)

    # Override dependency
    async def get_mock_cookie_service():
        return mock_cookie_service

    from app.api import admin

    app.dependency_overrides[admin.get_cookie_service] = get_mock_cookie_service

    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestValidateCookieEndpoint:
    """Test /api/v1/admin/validate-cookie endpoint."""

    def test_validate_cookie_success(self, client, mock_cookie_service):
        """Test successful cookie validation."""
        mock_cookie_service.validate_cookie.return_value = True
        mock_cookie_service.get_cookie_age_hours.return_value = 2.5
        mock_cookie_service.check_cookie_age.return_value = None

        response = client.post("/api/v1/admin/validate-cookie", json={"provider": "youtube"})

        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "youtube"
        assert data["is_valid"] is True
        assert data["age_hours"] == 2.5
        assert data["warning"] is None

    def test_validate_cookie_with_warning(self, client, mock_cookie_service):
        """Test cookie validation with age warning."""
        mock_cookie_service.validate_cookie.return_value = True
        mock_cookie_service.get_cookie_age_hours.return_value = 200.0
        mock_cookie_service.check_cookie_age.return_value = "Cookie is 8 days old"

        response = client.post("/api/v1/admin/validate-cookie", json={"provider": "youtube"})

        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is True
        assert data["warning"] == "Cookie is 8 days old"

    def test_validate_cookie_failure(self, client, mock_cookie_service):
        """Test cookie validation failure."""
        mock_cookie_service.validate_cookie.side_effect = CookieError("Cookie file not found")

        response = client.post("/api/v1/admin/validate-cookie", json={"provider": "youtube"})

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error_code"] == "COOKIE_VALIDATION_FAILED"
        assert "Cookie file not found" in data["detail"]["message"]

    def test_validate_cookie_internal_error(self, client, mock_cookie_service):
        """Test cookie validation with unexpected error."""
        mock_cookie_service.validate_cookie.side_effect = Exception("Unexpected error")

        response = client.post("/api/v1/admin/validate-cookie", json={"provider": "youtube"})

        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["error_code"] == "INTERNAL_ERROR"


class TestReloadCookieEndpoint:
    """Test /api/v1/admin/reload-cookie endpoint."""

    def test_reload_cookie_success(self, client, mock_cookie_service):
        """Test successful cookie reload."""
        mock_cookie_service.reload_cookie.return_value = {
            "success": True,
            "provider": "youtube",
            "message": "Cookie reloaded successfully",
            "age_hours": 1.5,
        }

        response = client.post("/api/v1/admin/reload-cookie", json={"provider": "youtube"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["provider"] == "youtube"
        assert "reloaded successfully" in data["message"]
        assert data["age_hours"] == 1.5

    def test_reload_cookie_validation_failure(self, client, mock_cookie_service):
        """Test cookie reload with validation failure."""
        mock_cookie_service.reload_cookie.side_effect = CookieError("New cookie failed validation")

        response = client.post("/api/v1/admin/reload-cookie", json={"provider": "youtube"})

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error_code"] == "COOKIE_RELOAD_FAILED"
        assert "failed validation" in data["detail"]["message"]

    def test_reload_cookie_provider_not_found(self, client, mock_cookie_service):
        """Test reload for non-existent provider."""
        mock_cookie_service.reload_cookie.side_effect = CookieError(
            "Provider 'nonexistent' not configured"
        )

        response = client.post("/api/v1/admin/reload-cookie", json={"provider": "nonexistent"})

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error_code"] == "COOKIE_RELOAD_FAILED"

    def test_reload_cookie_internal_error(self, client, mock_cookie_service):
        """Test cookie reload with unexpected error."""
        mock_cookie_service.reload_cookie.side_effect = Exception("Unexpected error")

        response = client.post("/api/v1/admin/reload-cookie", json={"provider": "youtube"})

        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["error_code"] == "INTERNAL_ERROR"


class TestEndpointIntegration:
    """Test endpoint integration scenarios."""

    def test_validate_then_reload_workflow(self, client, mock_cookie_service):
        """Test typical workflow: validate, then reload."""
        # First validation fails
        mock_cookie_service.validate_cookie.side_effect = CookieError("Cookie expired")

        response1 = client.post("/api/v1/admin/validate-cookie", json={"provider": "youtube"})
        assert response1.status_code == 400

        # Reload cookie
        mock_cookie_service.reload_cookie.return_value = {
            "success": True,
            "provider": "youtube",
            "message": "Cookie reloaded",
            "age_hours": 0.1,
        }

        response2 = client.post("/api/v1/admin/reload-cookie", json={"provider": "youtube"})
        assert response2.status_code == 200

        # Validation now succeeds
        mock_cookie_service.validate_cookie.side_effect = None
        mock_cookie_service.validate_cookie.return_value = True
        mock_cookie_service.get_cookie_age_hours.return_value = 0.1
        mock_cookie_service.check_cookie_age.return_value = None

        response3 = client.post("/api/v1/admin/validate-cookie", json={"provider": "youtube"})
        assert response3.status_code == 200
        assert response3.json()["is_valid"] is True
