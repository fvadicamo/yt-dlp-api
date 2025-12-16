"""Rate limiting implementation using token bucket algorithm.

This module provides per-API-key, per-category rate limiting with burst support.
Satisfies Requirement 27: Rate Limiting.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class TokenBucket:
    """Token bucket for rate limiting.

    Attributes:
        capacity: Maximum number of tokens (burst capacity)
        refill_rate: Tokens added per second
        tokens: Current token count
        last_refill: Timestamp of last refill
    """

    capacity: int
    refill_rate: float
    tokens: float = field(default=0.0)
    last_refill: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        """Initialize tokens to capacity if not set."""
        if self.tokens == 0.0:
            self.tokens = float(self.capacity)


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit category.

    Attributes:
        rpm: Requests per minute
        burst_capacity: Maximum burst size (tokens)
    """

    rpm: int
    burst_capacity: int = 20


class RateLimiter:
    """Token bucket rate limiter with per-API-key, per-category limits.

    Supports separate limits for metadata (100 rpm) and download (10 rpm) operations
    with burst capacity for handling traffic spikes.

    Example:
        limiter = RateLimiter()
        allowed, retry_after = await limiter.check_rate_limit("api-key-123", "metadata")
        if not allowed:
            # Return 429 with Retry-After header
            pass
    """

    # Default limits per endpoint category
    DEFAULT_LIMITS: Dict[str, RateLimitConfig] = {
        "metadata": RateLimitConfig(rpm=100, burst_capacity=20),
        "download": RateLimitConfig(rpm=10, burst_capacity=20),
    }

    # Endpoint path to category mapping
    ENDPOINT_CATEGORIES: Dict[str, str] = {
        "/api/v1/info": "metadata",
        "/api/v1/formats": "metadata",
        "/api/v1/download": "download",
    }

    def __init__(
        self,
        limits: Optional[Dict[str, RateLimitConfig]] = None,
        endpoint_categories: Optional[Dict[str, str]] = None,
    ) -> None:
        """Initialize rate limiter.

        Args:
            limits: Custom limits per category. Uses DEFAULT_LIMITS if not provided.
            endpoint_categories: Custom endpoint to category mapping.
        """
        self.limits = limits or self.DEFAULT_LIMITS.copy()
        self.endpoint_categories = endpoint_categories or self.ENDPOINT_CATEGORIES.copy()
        self._buckets: Dict[str, Dict[str, TokenBucket]] = defaultdict(dict)

    def configure_limits(
        self,
        metadata_rpm: Optional[int] = None,
        download_rpm: Optional[int] = None,
        burst_capacity: Optional[int] = None,
    ) -> None:
        """Configure rate limits from config values.

        Args:
            metadata_rpm: Requests per minute for metadata operations
            download_rpm: Requests per minute for download operations
            burst_capacity: Burst capacity for all categories
        """
        if metadata_rpm is not None:
            self.limits["metadata"] = RateLimitConfig(
                rpm=metadata_rpm,
                burst_capacity=burst_capacity or self.limits["metadata"].burst_capacity,
            )
        if download_rpm is not None:
            self.limits["download"] = RateLimitConfig(
                rpm=download_rpm,
                burst_capacity=burst_capacity or self.limits["download"].burst_capacity,
            )
        if burst_capacity is not None:
            for category in self.limits:
                self.limits[category] = RateLimitConfig(
                    rpm=self.limits[category].rpm,
                    burst_capacity=burst_capacity,
                )

    def get_endpoint_category(self, path: str) -> Optional[str]:
        """Determine the rate limit category for an endpoint path.

        Args:
            path: The request URL path

        Returns:
            Category name or None if path is not rate limited
        """
        # Normalize path
        path = path.rstrip("/")

        # Direct match
        if path in self.endpoint_categories:
            return self.endpoint_categories[path]

        # Prefix match for paths like /api/v1/info?url=...
        for endpoint, category in self.endpoint_categories.items():
            if path.startswith(endpoint):
                return category

        return None

    def _get_bucket(self, api_key: str, category: str) -> TokenBucket:
        """Get or create a token bucket for an API key and category.

        Args:
            api_key: The API key identifier
            category: The rate limit category

        Returns:
            TokenBucket for this key/category combination
        """
        if category not in self._buckets[api_key]:
            config = self.limits.get(category)
            if config is None:
                # Unknown category, use metadata limits as default
                config = self.limits["metadata"]

            self._buckets[api_key][category] = TokenBucket(
                capacity=config.burst_capacity,
                refill_rate=config.rpm / 60.0,  # Convert RPM to tokens per second
            )
        return self._buckets[api_key][category]

    def _refill_bucket(self, bucket: TokenBucket) -> None:
        """Refill a token bucket based on elapsed time.

        Args:
            bucket: The bucket to refill
        """
        now = time.time()
        elapsed = now - bucket.last_refill
        tokens_to_add = elapsed * bucket.refill_rate

        bucket.tokens = min(bucket.capacity, bucket.tokens + tokens_to_add)
        bucket.last_refill = now

    async def check_rate_limit(
        self,
        api_key: str,
        category: str,
    ) -> Tuple[bool, float]:
        """Check if a request is allowed under the rate limit.

        Args:
            api_key: The API key making the request
            category: The rate limit category (e.g., "metadata", "download")

        Returns:
            Tuple of (allowed, retry_after_seconds)
            - allowed: True if request is within rate limit
            - retry_after_seconds: Seconds to wait before retry (0 if allowed)
        """
        bucket = self._get_bucket(api_key, category)
        self._refill_bucket(bucket)

        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            logger.debug(
                "rate_limit_check_passed",
                category=category,
                tokens_remaining=bucket.tokens,
            )
            return True, 0.0
        else:
            # Calculate retry after
            tokens_needed = 1.0 - bucket.tokens
            retry_after = tokens_needed / bucket.refill_rate

            logger.info(
                "rate_limit_exceeded",
                category=category,
                retry_after=retry_after,
                tokens_available=bucket.tokens,
            )
            return False, retry_after

    def get_bucket_status(self, api_key: str, category: str) -> Dict:
        """Get current status of a rate limit bucket.

        Args:
            api_key: The API key
            category: The rate limit category

        Returns:
            Dict with bucket status including tokens, capacity, and limits
        """
        if api_key not in self._buckets or category not in self._buckets[api_key]:
            config = self.limits.get(category, self.limits["metadata"])
            return {
                "tokens": config.burst_capacity,
                "capacity": config.burst_capacity,
                "refill_rate": config.rpm / 60.0,
                "rpm": config.rpm,
            }

        bucket = self._buckets[api_key][category]
        self._refill_bucket(bucket)

        return {
            "tokens": bucket.tokens,
            "capacity": bucket.capacity,
            "refill_rate": bucket.refill_rate,
            "rpm": int(bucket.refill_rate * 60),
        }

    def reset_bucket(self, api_key: str, category: Optional[str] = None) -> None:
        """Reset rate limit bucket(s) for an API key.

        Args:
            api_key: The API key
            category: Specific category to reset, or None for all categories
        """
        if api_key in self._buckets:
            if category:
                if category in self._buckets[api_key]:
                    del self._buckets[api_key][category]
            else:
                del self._buckets[api_key]

    def clear_all_buckets(self) -> None:
        """Clear all rate limit buckets. Useful for testing."""
        self._buckets.clear()


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance.

    Returns:
        The configured RateLimiter instance
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def configure_rate_limiter(
    metadata_rpm: Optional[int] = None,
    download_rpm: Optional[int] = None,
    burst_capacity: Optional[int] = None,
) -> RateLimiter:
    """Configure the global rate limiter with custom settings.

    Args:
        metadata_rpm: Requests per minute for metadata operations
        download_rpm: Requests per minute for download operations
        burst_capacity: Burst capacity for all categories

    Returns:
        The configured RateLimiter instance
    """
    global _rate_limiter
    _rate_limiter = RateLimiter()
    _rate_limiter.configure_limits(
        metadata_rpm=metadata_rpm,
        download_rpm=download_rpm,
        burst_capacity=burst_capacity,
    )
    return _rate_limiter
