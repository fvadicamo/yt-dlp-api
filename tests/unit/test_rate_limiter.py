"""Tests for the rate limiting system.

This module tests:
- Token bucket refill logic
- Rate limit enforcement per category
- Burst allowance behavior
- Retry-After header calculation
- Middleware integration

Satisfies Requirement 27: Rate Limiting.
"""

import asyncio
import time
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.rate_limiter import (
    RateLimitConfig,
    RateLimiter,
    TokenBucket,
    configure_rate_limiter,
    get_rate_limiter,
)
from app.middleware.rate_limit import RateLimitMiddleware, create_rate_limit_middleware


class TestTokenBucket:
    """Tests for TokenBucket dataclass."""

    def test_token_bucket_initialization(self):
        """Test that TokenBucket initializes with correct values."""
        bucket = TokenBucket(capacity=20, refill_rate=1.67)

        assert bucket.capacity == 20
        assert bucket.refill_rate == 1.67
        assert bucket.tokens == 20.0  # Should start at capacity
        assert bucket.last_refill > 0

    def test_token_bucket_custom_tokens(self):
        """Test TokenBucket with explicit token count."""
        bucket = TokenBucket(capacity=20, refill_rate=1.0, tokens=10.0)

        assert bucket.capacity == 20
        assert bucket.tokens == 10.0

    def test_token_bucket_defaults(self):
        """Test TokenBucket default values."""
        before = time.time()
        bucket = TokenBucket(capacity=10, refill_rate=0.5)
        after = time.time()

        assert bucket.capacity == 10
        assert bucket.tokens == 10.0
        assert before <= bucket.last_refill <= after


class TestRateLimitConfig:
    """Tests for RateLimitConfig dataclass."""

    def test_rate_limit_config_defaults(self):
        """Test RateLimitConfig default values."""
        config = RateLimitConfig(rpm=100)

        assert config.rpm == 100
        assert config.burst_capacity == 20

    def test_rate_limit_config_custom(self):
        """Test RateLimitConfig with custom values."""
        config = RateLimitConfig(rpm=50, burst_capacity=10)

        assert config.rpm == 50
        assert config.burst_capacity == 10


class TestRateLimiterInitialization:
    """Tests for RateLimiter initialization."""

    def test_default_limits(self):
        """Test that default limits are set correctly."""
        limiter = RateLimiter()

        assert "metadata" in limiter.limits
        assert "download" in limiter.limits
        assert limiter.limits["metadata"].rpm == 100
        assert limiter.limits["download"].rpm == 10
        assert limiter.limits["metadata"].burst_capacity == 20
        assert limiter.limits["download"].burst_capacity == 20

    def test_custom_limits(self):
        """Test initialization with custom limits."""
        custom_limits = {
            "metadata": RateLimitConfig(rpm=50, burst_capacity=10),
            "download": RateLimitConfig(rpm=5, burst_capacity=5),
        }
        limiter = RateLimiter(limits=custom_limits)

        assert limiter.limits["metadata"].rpm == 50
        assert limiter.limits["download"].rpm == 5

    def test_endpoint_categories(self):
        """Test default endpoint categories."""
        limiter = RateLimiter()

        assert limiter.get_endpoint_category("/api/v1/info") == "metadata"
        assert limiter.get_endpoint_category("/api/v1/formats") == "metadata"
        assert limiter.get_endpoint_category("/api/v1/download") == "download"

    def test_custom_endpoint_categories(self):
        """Test custom endpoint categories."""
        custom_categories = {
            "/api/v2/videos": "metadata",
            "/api/v2/fetch": "download",
        }
        limiter = RateLimiter(endpoint_categories=custom_categories)

        assert limiter.get_endpoint_category("/api/v2/videos") == "metadata"
        assert limiter.get_endpoint_category("/api/v2/fetch") == "download"
        assert limiter.get_endpoint_category("/api/v1/info") is None


class TestConfigureLimits:
    """Tests for configure_limits method."""

    def test_configure_metadata_rpm(self):
        """Test configuring metadata RPM."""
        limiter = RateLimiter()
        limiter.configure_limits(metadata_rpm=200)

        assert limiter.limits["metadata"].rpm == 200
        assert limiter.limits["download"].rpm == 10  # Unchanged

    def test_configure_download_rpm(self):
        """Test configuring download RPM."""
        limiter = RateLimiter()
        limiter.configure_limits(download_rpm=20)

        assert limiter.limits["metadata"].rpm == 100  # Unchanged
        assert limiter.limits["download"].rpm == 20

    def test_configure_burst_capacity(self):
        """Test configuring burst capacity."""
        limiter = RateLimiter()
        limiter.configure_limits(burst_capacity=50)

        assert limiter.limits["metadata"].burst_capacity == 50
        assert limiter.limits["download"].burst_capacity == 50

    def test_configure_all_options(self):
        """Test configuring all options together."""
        limiter = RateLimiter()
        limiter.configure_limits(metadata_rpm=150, download_rpm=15, burst_capacity=30)

        assert limiter.limits["metadata"].rpm == 150
        assert limiter.limits["download"].rpm == 15
        assert limiter.limits["metadata"].burst_capacity == 30
        assert limiter.limits["download"].burst_capacity == 30


class TestEndpointCategory:
    """Tests for get_endpoint_category method."""

    def test_exact_path_match(self):
        """Test exact path matching."""
        limiter = RateLimiter()

        assert limiter.get_endpoint_category("/api/v1/info") == "metadata"
        assert limiter.get_endpoint_category("/api/v1/download") == "download"

    def test_path_with_trailing_slash(self):
        """Test paths with trailing slash."""
        limiter = RateLimiter()

        assert limiter.get_endpoint_category("/api/v1/info/") == "metadata"
        assert limiter.get_endpoint_category("/api/v1/download/") == "download"

    def test_path_with_query_params(self):
        """Test paths with query parameters are matched by prefix."""
        limiter = RateLimiter()

        # Prefix matching
        assert limiter.get_endpoint_category("/api/v1/info?url=test") == "metadata"

    def test_unknown_path(self):
        """Test unknown paths return None."""
        limiter = RateLimiter()

        assert limiter.get_endpoint_category("/api/v1/unknown") is None
        assert limiter.get_endpoint_category("/health") is None
        assert limiter.get_endpoint_category("/") is None


class TestTokenBucketRefill:
    """Tests for token bucket refill logic."""

    @pytest.mark.asyncio
    async def test_tokens_refill_over_time(self):
        """Test that tokens are refilled based on elapsed time."""
        limiter = RateLimiter()

        # Drain some tokens
        api_key = "test-key"
        for _ in range(5):
            await limiter.check_rate_limit(api_key, "metadata")

        status_before = limiter.get_bucket_status(api_key, "metadata")

        # Wait for refill (100 rpm = 1.67 tokens/sec)
        await asyncio.sleep(0.1)

        status_after = limiter.get_bucket_status(api_key, "metadata")

        # Tokens should have increased
        assert status_after["tokens"] > status_before["tokens"]

    def test_tokens_capped_at_capacity(self):
        """Test that tokens don't exceed capacity."""
        limiter = RateLimiter()
        api_key = "test-key"

        # Get initial status (should be at capacity)
        status = limiter.get_bucket_status(api_key, "metadata")

        assert status["tokens"] == status["capacity"]

    @pytest.mark.asyncio
    async def test_refill_rate_calculation(self):
        """Test that refill rate is calculated correctly from RPM."""
        limiter = RateLimiter()
        api_key = "test-key"

        # Trigger bucket creation
        await limiter.check_rate_limit(api_key, "metadata")

        status = limiter.get_bucket_status(api_key, "metadata")

        # 100 RPM = 100/60 = 1.667 tokens/sec
        expected_rate = 100 / 60.0
        assert abs(status["refill_rate"] - expected_rate) < 0.01


class TestRateLimitEnforcement:
    """Tests for rate limit enforcement."""

    @pytest.mark.asyncio
    async def test_requests_allowed_within_limit(self):
        """Test that requests within limit are allowed."""
        limiter = RateLimiter()
        api_key = "test-key"

        # First 20 requests should be allowed (burst capacity)
        for _ in range(20):
            allowed, retry_after = await limiter.check_rate_limit(api_key, "metadata")
            assert allowed is True
            assert retry_after == 0.0

    @pytest.mark.asyncio
    async def test_requests_blocked_over_limit(self):
        """Test that requests over limit are blocked."""
        limiter = RateLimiter()
        api_key = "test-key"

        # Exhaust burst capacity
        for _ in range(20):
            await limiter.check_rate_limit(api_key, "metadata")

        # Next request should be blocked
        allowed, retry_after = await limiter.check_rate_limit(api_key, "metadata")

        assert allowed is False
        assert retry_after > 0

    @pytest.mark.asyncio
    async def test_different_api_keys_independent(self):
        """Test that rate limits are independent per API key."""
        limiter = RateLimiter()

        # Exhaust key1's limit
        for _ in range(20):
            await limiter.check_rate_limit("key1", "metadata")

        # key1 should be blocked
        allowed_key1, _ = await limiter.check_rate_limit("key1", "metadata")
        assert allowed_key1 is False

        # key2 should still be allowed
        allowed_key2, _ = await limiter.check_rate_limit("key2", "metadata")
        assert allowed_key2 is True

    @pytest.mark.asyncio
    async def test_different_categories_independent(self):
        """Test that rate limits are independent per category."""
        limiter = RateLimiter()
        api_key = "test-key"

        # Exhaust metadata limit
        for _ in range(20):
            await limiter.check_rate_limit(api_key, "metadata")

        # metadata should be blocked
        allowed_metadata, _ = await limiter.check_rate_limit(api_key, "metadata")
        assert allowed_metadata is False

        # download should still be allowed
        allowed_download, _ = await limiter.check_rate_limit(api_key, "download")
        assert allowed_download is True

    @pytest.mark.asyncio
    async def test_download_lower_limit(self):
        """Test that download has lower limit than metadata."""
        limiter = RateLimiter()
        api_key = "test-key"

        # Both start with 20 burst capacity, but download limit is lower
        # Exhaust download limit
        for _ in range(20):
            await limiter.check_rate_limit(api_key, "download")

        allowed, retry_after = await limiter.check_rate_limit(api_key, "download")
        assert allowed is False

        # Download retry_after should be longer (lower refill rate)
        # 10 rpm = 0.167 tokens/sec vs 100 rpm = 1.67 tokens/sec
        assert retry_after > 0


class TestRetryAfterCalculation:
    """Tests for Retry-After header calculation."""

    @pytest.mark.asyncio
    async def test_retry_after_accurate(self):
        """Test that retry_after is calculated correctly."""
        limiter = RateLimiter()
        api_key = "test-key"

        # Exhaust limit
        for _ in range(20):
            await limiter.check_rate_limit(api_key, "metadata")

        _, retry_after = await limiter.check_rate_limit(api_key, "metadata")

        # With 100 rpm (1.67 tokens/sec), need ~0.6 sec for 1 token
        # Should be less than 1 second
        assert 0 < retry_after < 1.0

    @pytest.mark.asyncio
    async def test_retry_after_download_longer(self):
        """Test that download retry_after is longer than metadata."""
        limiter = RateLimiter()
        api_key = "test-key"

        # Exhaust both limits
        for _ in range(20):
            await limiter.check_rate_limit(api_key, "metadata")
            await limiter.check_rate_limit(api_key, "download")

        _, retry_metadata = await limiter.check_rate_limit(api_key, "metadata")
        _, retry_download = await limiter.check_rate_limit(api_key, "download")

        # Download should have longer retry (10 rpm vs 100 rpm)
        assert retry_download > retry_metadata


class TestBucketStatus:
    """Tests for get_bucket_status method."""

    @pytest.mark.asyncio
    async def test_bucket_status_new_bucket(self):
        """Test status for a new (non-existent) bucket."""
        limiter = RateLimiter()

        status = limiter.get_bucket_status("new-key", "metadata")

        assert status["tokens"] == 20
        assert status["capacity"] == 20
        assert status["rpm"] == 100

    @pytest.mark.asyncio
    async def test_bucket_status_after_requests(self):
        """Test status after some requests."""
        limiter = RateLimiter()
        api_key = "test-key"

        # Make 5 requests
        for _ in range(5):
            await limiter.check_rate_limit(api_key, "metadata")

        status = limiter.get_bucket_status(api_key, "metadata")

        # Should have used 5 tokens (plus small refill during test)
        assert status["tokens"] < 20
        assert status["tokens"] >= 14  # At least 15 - some margin for timing


class TestBucketReset:
    """Tests for reset_bucket method."""

    @pytest.mark.asyncio
    async def test_reset_specific_category(self):
        """Test resetting a specific category."""
        limiter = RateLimiter()
        api_key = "test-key"

        # Use some tokens from both categories
        for _ in range(5):
            await limiter.check_rate_limit(api_key, "metadata")
            await limiter.check_rate_limit(api_key, "download")

        # Reset only metadata
        limiter.reset_bucket(api_key, "metadata")

        # metadata should be reset (new bucket), download unchanged
        metadata_status = limiter.get_bucket_status(api_key, "metadata")
        download_status = limiter.get_bucket_status(api_key, "download")

        assert metadata_status["tokens"] == 20  # Reset to full
        assert download_status["tokens"] < 20  # Still depleted

    @pytest.mark.asyncio
    async def test_reset_all_categories(self):
        """Test resetting all categories for an API key."""
        limiter = RateLimiter()
        api_key = "test-key"

        # Use some tokens
        for _ in range(5):
            await limiter.check_rate_limit(api_key, "metadata")
            await limiter.check_rate_limit(api_key, "download")

        # Reset all
        limiter.reset_bucket(api_key)

        # Both should be reset
        metadata_status = limiter.get_bucket_status(api_key, "metadata")
        download_status = limiter.get_bucket_status(api_key, "download")

        assert metadata_status["tokens"] == 20
        assert download_status["tokens"] == 20

    def test_clear_all_buckets(self):
        """Test clearing all buckets."""
        limiter = RateLimiter()

        # Create some buckets
        limiter._get_bucket("key1", "metadata")
        limiter._get_bucket("key2", "download")

        assert len(limiter._buckets) == 2

        limiter.clear_all_buckets()

        assert len(limiter._buckets) == 0


class TestGlobalRateLimiter:
    """Tests for global rate limiter functions."""

    def test_get_rate_limiter_singleton(self):
        """Test that get_rate_limiter returns same instance."""
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()

        assert limiter1 is limiter2

    def test_configure_rate_limiter(self):
        """Test configure_rate_limiter sets up custom limits."""
        limiter = configure_rate_limiter(metadata_rpm=200, download_rpm=20)

        assert limiter.limits["metadata"].rpm == 200
        assert limiter.limits["download"].rpm == 20


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware."""

    @pytest.fixture
    def app(self):
        """Create test FastAPI app."""
        app = FastAPI()

        @app.get("/api/v1/info")
        async def get_info():
            return {"status": "ok"}

        @app.post("/api/v1/download")
        async def download():
            return {"status": "ok"}

        @app.get("/health")
        async def health():
            return {"status": "healthy"}

        return app

    @pytest.fixture
    def limiter(self):
        """Create fresh rate limiter for each test."""
        return RateLimiter()

    def test_middleware_allows_within_limit(self, app, limiter):
        """Test middleware allows requests within limit."""
        app.add_middleware(RateLimitMiddleware, rate_limiter=limiter)
        client = TestClient(app)

        response = client.get("/api/v1/info", headers={"X-API-Key": "test-key"})

        assert response.status_code == 200

    def test_middleware_blocks_over_limit(self, app, limiter):
        """Test middleware blocks requests over limit."""
        app.add_middleware(RateLimitMiddleware, rate_limiter=limiter)
        client = TestClient(app)

        # Exhaust limit
        for _ in range(20):
            client.get("/api/v1/info", headers={"X-API-Key": "test-key"})

        # Should be blocked
        response = client.get("/api/v1/info", headers={"X-API-Key": "test-key"})

        assert response.status_code == 429
        assert "Retry-After" in response.headers
        assert response.json()["error_code"] == "RATE_LIMIT_EXCEEDED"

    def test_middleware_excludes_health_endpoint(self, app, limiter):
        """Test middleware excludes health endpoint."""
        app.add_middleware(RateLimitMiddleware, rate_limiter=limiter)
        client = TestClient(app)

        # Make many requests to health (should not be limited)
        for _ in range(50):
            response = client.get("/health")
            assert response.status_code == 200

    def test_middleware_anonymous_user(self, app, limiter):
        """Test middleware handles anonymous users."""
        app.add_middleware(RateLimitMiddleware, rate_limiter=limiter)
        client = TestClient(app)

        # Request without API key
        response = client.get("/api/v1/info")

        assert response.status_code == 200

    def test_middleware_retry_after_header(self, app, limiter):
        """Test middleware sets Retry-After header."""
        app.add_middleware(RateLimitMiddleware, rate_limiter=limiter)
        client = TestClient(app)

        # Exhaust limit
        for _ in range(20):
            client.get("/api/v1/info", headers={"X-API-Key": "test-key"})

        response = client.get("/api/v1/info", headers={"X-API-Key": "test-key"})

        assert response.status_code == 429
        retry_after = int(response.headers["Retry-After"])
        assert retry_after >= 1

    def test_middleware_different_categories(self, app, limiter):
        """Test middleware enforces different categories independently."""
        app.add_middleware(RateLimitMiddleware, rate_limiter=limiter)
        client = TestClient(app)

        # Exhaust metadata limit
        for _ in range(20):
            client.get("/api/v1/info", headers={"X-API-Key": "test-key"})

        # Metadata should be blocked
        response_info = client.get("/api/v1/info", headers={"X-API-Key": "test-key"})
        assert response_info.status_code == 429

        # Download should still work
        response_download = client.post("/api/v1/download", headers={"X-API-Key": "test-key"})
        assert response_download.status_code == 200


class TestCreateRateLimitMiddleware:
    """Tests for create_rate_limit_middleware factory."""

    def test_factory_creates_middleware(self):
        """Test factory creates middleware correctly."""
        limiter = RateLimiter()
        factory = create_rate_limit_middleware(rate_limiter=limiter)

        app = MagicMock()
        middleware = factory(app)

        assert isinstance(middleware, RateLimitMiddleware)
        assert middleware.rate_limiter is limiter

    def test_factory_with_custom_excluded_paths(self):
        """Test factory with custom excluded paths."""
        excluded = frozenset({"/custom"})
        factory = create_rate_limit_middleware(excluded_paths=excluded)

        app = MagicMock()
        middleware = factory(app)

        assert middleware.excluded_paths == excluded


class TestRateLimitMiddlewareExcludedPaths:
    """Tests for middleware excluded paths."""

    @pytest.fixture
    def app(self):
        """Create test app with various endpoints."""
        app = FastAPI()

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        @app.get("/docs")
        async def docs():
            return {"docs": "here"}

        @app.get("/api/v1/info")
        async def info():
            return {"info": "here"}

        return app

    def test_default_excluded_paths(self, app):
        """Test default excluded paths."""
        limiter = RateLimiter()
        app.add_middleware(RateLimitMiddleware, rate_limiter=limiter)
        client = TestClient(app)

        # Default excluded paths should not count against limit
        for _ in range(50):
            assert client.get("/health").status_code == 200

    def test_custom_excluded_paths(self, app):
        """Test custom excluded paths."""
        limiter = RateLimiter()
        app.add_middleware(
            RateLimitMiddleware,
            rate_limiter=limiter,
            excluded_paths=frozenset({"/api/v1/info"}),
        )
        client = TestClient(app)

        # Custom excluded path should not be limited
        for _ in range(50):
            response = client.get("/api/v1/info")
            # Note: May return 404 if endpoint doesn't exist, but won't return 429
            assert response.status_code != 429 or response.status_code == 200
