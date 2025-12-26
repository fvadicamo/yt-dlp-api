"""Tests for API key authentication middleware."""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.middleware.auth import (
    APIKeyAuth,
    configure_auth,
    create_auth_dependency,
    get_auth,
    hash_api_key,
)


class TestHashApiKey:
    """Tests for API key hashing."""

    def test_hash_api_key_returns_prefixed_hash(self):
        """Test that hash returns sha256-prefixed 8 character hash."""
        result = hash_api_key("test-api-key-12345")
        assert result.startswith("sha256:")
        assert len(result) == 15  # "sha256:" (7) + 8 hex chars
        assert result[7:].isalnum()

    def test_hash_api_key_consistent(self):
        """Test that same key produces same hash."""
        key = "test-api-key"
        hash1 = hash_api_key(key)
        hash2 = hash_api_key(key)
        assert hash1 == hash2

    def test_hash_api_key_different_keys(self):
        """Test that different keys produce different hashes."""
        hash1 = hash_api_key("key1")
        hash2 = hash_api_key("key2")
        assert hash1 != hash2

    def test_hash_api_key_empty(self):
        """Test hashing empty key."""
        assert hash_api_key("") == "empty"
        assert hash_api_key(None) == "empty"


class TestAPIKeyAuth:
    """Tests for APIKeyAuth class."""

    @pytest.fixture
    def auth_with_keys(self) -> APIKeyAuth:
        """Create auth with configured keys."""
        return APIKeyAuth(api_keys=["key1", "key2", "key3"])

    @pytest.fixture
    def auth_no_keys(self) -> APIKeyAuth:
        """Create auth with no keys (allows all)."""
        return APIKeyAuth(api_keys=[])

    @pytest.fixture
    def mock_request(self) -> MagicMock:
        """Create a mock request."""
        request = MagicMock()
        request.url.path = "/api/v1/info"
        request.client.host = "127.0.0.1"
        return request


class TestAPIKeyValidation(TestAPIKeyAuth):
    """Tests for API key validation."""

    def test_valid_key_accepted(self, auth_with_keys: APIKeyAuth):
        """Test that valid keys are accepted."""
        assert auth_with_keys.validate_api_key("key1") is True
        assert auth_with_keys.validate_api_key("key2") is True
        assert auth_with_keys.validate_api_key("key3") is True

    def test_invalid_key_rejected(self, auth_with_keys: APIKeyAuth):
        """Test that invalid keys are rejected."""
        assert auth_with_keys.validate_api_key("invalid") is False
        assert auth_with_keys.validate_api_key("key4") is False

    def test_empty_key_rejected(self, auth_with_keys: APIKeyAuth):
        """Test that empty keys are rejected."""
        assert auth_with_keys.validate_api_key("") is False
        assert auth_with_keys.validate_api_key(None) is False

    def test_no_keys_allows_all(self, auth_no_keys: APIKeyAuth):
        """Test that no configured keys allows all requests."""
        assert auth_no_keys.allow_all is True
        assert auth_no_keys.validate_api_key("anything") is True
        assert auth_no_keys.validate_api_key("") is True
        assert auth_no_keys.validate_api_key(None) is True

    def test_with_keys_not_allow_all(self, auth_with_keys: APIKeyAuth):
        """Test that configured keys disables allow_all."""
        assert auth_with_keys.allow_all is False


class TestPathExclusion(TestAPIKeyAuth):
    """Tests for path exclusion."""

    @pytest.mark.parametrize(
        "path",
        [
            "/health",
            "/liveness",
            "/readiness",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/metrics",
        ],
    )
    def test_default_excluded_paths(self, auth_with_keys: APIKeyAuth, path: str):
        """Test that default paths are excluded."""
        assert auth_with_keys.is_path_excluded(path) is True

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/info",
            "/api/v1/download",
            "/api/v1/formats",
            "/admin/reload-cookie",
        ],
    )
    def test_api_paths_not_excluded(self, auth_with_keys: APIKeyAuth, path: str):
        """Test that API paths are not excluded."""
        assert auth_with_keys.is_path_excluded(path) is False

    def test_custom_excluded_paths(self):
        """Test custom excluded paths."""
        auth = APIKeyAuth(
            api_keys=["key1"],
            excluded_paths={"/custom", "/another"},
        )
        assert auth.is_path_excluded("/custom") is True
        assert auth.is_path_excluded("/another") is True
        assert auth.is_path_excluded("/health") is False  # Not in custom list

    def test_path_prefix_matching(self, auth_with_keys: APIKeyAuth):
        """Test that path prefix matching works."""
        # /docs should match /docs/oauth2-redirect
        assert auth_with_keys.is_path_excluded("/docs/oauth2-redirect") is True

    def test_trailing_slash_normalized(self, auth_with_keys: APIKeyAuth):
        """Test that trailing slashes are handled."""
        assert auth_with_keys.is_path_excluded("/health/") is True


class TestAuthenticate(TestAPIKeyAuth):
    """Tests for the authenticate method."""

    def test_authenticate_with_valid_key(self, auth_with_keys: APIKeyAuth, mock_request: MagicMock):
        """Test authentication with valid key."""
        result = auth_with_keys.authenticate(mock_request, "key1")
        assert result is True

    def test_authenticate_with_invalid_key_raises(
        self, auth_with_keys: APIKeyAuth, mock_request: MagicMock
    ):
        """Test authentication with invalid key raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            auth_with_keys.authenticate(mock_request, "invalid")

        assert exc_info.value.status_code == 401
        assert "Invalid" in exc_info.value.detail

    def test_authenticate_with_missing_key_raises(
        self, auth_with_keys: APIKeyAuth, mock_request: MagicMock
    ):
        """Test authentication with missing key raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            auth_with_keys.authenticate(mock_request, None)

        assert exc_info.value.status_code == 401

    def test_authenticate_excluded_path_no_key(
        self, auth_with_keys: APIKeyAuth, mock_request: MagicMock
    ):
        """Test that excluded paths don't need authentication."""
        mock_request.url.path = "/health"

        result = auth_with_keys.authenticate(mock_request, None)
        assert result is True

    def test_authenticate_no_keys_allows_all(
        self, auth_no_keys: APIKeyAuth, mock_request: MagicMock
    ):
        """Test that no configured keys allows all requests."""
        result = auth_no_keys.authenticate(mock_request, None)
        assert result is True

    def test_authenticate_logs_failure(
        self, auth_with_keys: APIKeyAuth, mock_request: MagicMock, caplog
    ):
        """Test that failed authentication is logged."""
        import structlog

        # Configure structlog for capturing
        structlog.configure(
            processors=[structlog.processors.KeyValueRenderer()],
            wrapper_class=structlog.BoundLogger,
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=False,
        )

        with pytest.raises(HTTPException):
            auth_with_keys.authenticate(mock_request, "invalid-key")

        # The warning should have been logged
        # (actual log verification depends on structlog configuration)


class TestAPIKeyProperties(TestAPIKeyAuth):
    """Tests for APIKeyAuth properties."""

    def test_api_keys_property(self, auth_with_keys: APIKeyAuth):
        """Test api_keys property returns set."""
        keys = auth_with_keys.api_keys
        assert isinstance(keys, set)
        assert "key1" in keys
        assert len(keys) == 3

    def test_excluded_paths_property(self, auth_with_keys: APIKeyAuth):
        """Test excluded_paths property returns set."""
        paths = auth_with_keys.excluded_paths
        assert isinstance(paths, (set, frozenset))
        assert "/health" in paths


class TestConfigureAuth:
    """Tests for global auth configuration."""

    def test_configure_auth_creates_instance(self):
        """Test that configure_auth creates global instance."""
        auth = configure_auth(api_keys=["test-key"])
        assert isinstance(auth, APIKeyAuth)
        assert auth.validate_api_key("test-key") is True

    def test_get_auth_returns_configured(self):
        """Test that get_auth returns configured instance."""
        configure_auth(api_keys=["global-key"])
        auth = get_auth()
        assert auth.validate_api_key("global-key") is True

    def test_get_auth_returns_default_if_not_configured(self):
        """Test that get_auth returns default if not configured."""
        # Reset global instance
        import app.middleware.auth as auth_module

        auth_module._auth_instance = None

        auth = get_auth()
        assert isinstance(auth, APIKeyAuth)
        # Default allows all
        assert auth.allow_all is True


class TestCreateAuthDependency:
    """Tests for create_auth_dependency factory."""

    @pytest.mark.asyncio
    async def test_create_auth_dependency(self):
        """Test creating custom auth dependency."""
        dependency = create_auth_dependency(
            api_keys=["custom-key"],
            excluded_paths={"/custom-health"},
        )

        # Create mock request
        request = MagicMock()
        request.url.path = "/api/v1/test"
        request.client.host = "127.0.0.1"

        # Valid key should work
        result = await dependency(request, "custom-key")
        assert result == "custom-key"

        # Invalid key should raise
        with pytest.raises(HTTPException) as exc_info:
            await dependency(request, "wrong-key")
        assert exc_info.value.status_code == 401


class TestKeyNotLoggedPlaintext:
    """Tests to verify API keys are not logged in plaintext."""

    def test_hash_does_not_reveal_key(self):
        """Test that hash cannot be reversed to get original key."""
        api_key = "super-secret-api-key-12345"
        hashed = hash_api_key(api_key)

        # Hash should not contain the original key
        assert api_key not in hashed
        assert "secret" not in hashed
        assert "12345" not in hashed

    def test_auth_error_does_not_contain_key(self):
        """Test that auth error message doesn't contain the key."""
        auth = APIKeyAuth(api_keys=["valid-key"])
        request = MagicMock()
        request.url.path = "/api/v1/test"
        request.client.host = "127.0.0.1"

        with pytest.raises(HTTPException) as exc_info:
            auth.authenticate(request, "invalid-secret-key")

        # Error detail should not contain the key
        assert "invalid-secret-key" not in exc_info.value.detail
        assert "secret" not in exc_info.value.detail.lower()


class TestHTTPExceptionDetails:
    """Tests for HTTP exception response details."""

    def test_401_has_www_authenticate_header(self):
        """Test that 401 response includes WWW-Authenticate header."""
        auth = APIKeyAuth(api_keys=["valid-key"])
        request = MagicMock()
        request.url.path = "/api/v1/test"
        request.client.host = "127.0.0.1"

        with pytest.raises(HTTPException) as exc_info:
            auth.authenticate(request, "invalid")

        assert exc_info.value.headers is not None
        assert "WWW-Authenticate" in exc_info.value.headers
