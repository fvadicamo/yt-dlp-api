"""Rate limiting middleware for FastAPI.

This module provides HTTP middleware for enforcing rate limits on API requests.
Satisfies Requirement 27: Rate Limiting.
"""

from typing import Callable, FrozenSet, Optional

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.rate_limiter import RateLimiter, get_rate_limiter
from app.middleware.auth import hash_api_key

logger = structlog.get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """HTTP middleware for rate limiting API requests.

    This middleware checks each request against the rate limiter and returns
    HTTP 429 with Retry-After header when limits are exceeded.

    Excluded paths (health checks, docs, etc.) are not rate limited.
    """

    # Paths that don't require rate limiting
    DEFAULT_EXCLUDED_PATHS: FrozenSet[str] = frozenset(
        {
            "/health",
            "/liveness",
            "/readiness",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/metrics",
        }
    )

    def __init__(
        self,
        app: ASGIApp,
        rate_limiter: Optional[RateLimiter] = None,
        excluded_paths: Optional[FrozenSet[str]] = None,
    ) -> None:
        """Initialize rate limit middleware.

        Args:
            app: The ASGI application
            rate_limiter: RateLimiter instance. Uses global instance if not provided.
            excluded_paths: Paths to exclude from rate limiting.
        """
        super().__init__(app)
        self.rate_limiter = rate_limiter or get_rate_limiter()
        self.excluded_paths = excluded_paths or self.DEFAULT_EXCLUDED_PATHS

    def _is_excluded_path(self, path: str) -> bool:
        """Check if path should be excluded from rate limiting.

        Args:
            path: The request path

        Returns:
            True if path should be excluded
        """
        # Normalize path
        normalized = path.rstrip("/")

        # Direct match or prefix match
        return normalized in self.excluded_paths or any(
            normalized.startswith(excluded) for excluded in self.excluded_paths
        )

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Process request through rate limiting.

        Args:
            request: The incoming request
            call_next: The next middleware/handler in chain

        Returns:
            Response from next handler or 429 if rate limited
        """
        path = request.url.path

        # Skip excluded paths
        if self._is_excluded_path(path):
            return await call_next(request)

        # Get category for this endpoint
        category = self.rate_limiter.get_endpoint_category(path)
        if category is None:
            # Path not configured for rate limiting
            return await call_next(request)

        # Get API key from header (use "anonymous" if not provided)
        api_key = request.headers.get("X-API-Key", "anonymous")

        # Check rate limit
        allowed, retry_after = await self.rate_limiter.check_rate_limit(api_key, category)

        if not allowed:
            # Log rate limit exceeded
            logger.warning(
                "rate_limit_exceeded",
                path=path,
                category=category,
                api_key_hash=hash_api_key(api_key),
                retry_after=retry_after,
                client_ip=request.client.host if request.client else "unknown",
            )

            # Return 429 Too Many Requests
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(int(retry_after) + 1)},
                content={
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Rate limit exceeded for {category} operations",
                    "retry_after": retry_after,
                },
            )

        # Process request
        return await call_next(request)


def create_rate_limit_middleware(
    rate_limiter: Optional[RateLimiter] = None,
    excluded_paths: Optional[FrozenSet[str]] = None,
) -> Callable[[ASGIApp], RateLimitMiddleware]:
    """Factory function to create rate limit middleware with custom config.

    Args:
        rate_limiter: RateLimiter instance to use
        excluded_paths: Paths to exclude from rate limiting

    Returns:
        Middleware class configured with provided options
    """

    def middleware_factory(app: ASGIApp) -> RateLimitMiddleware:
        return RateLimitMiddleware(
            app,
            rate_limiter=rate_limiter,
            excluded_paths=excluded_paths,
        )

    return middleware_factory
