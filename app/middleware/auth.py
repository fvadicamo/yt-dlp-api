"""API key authentication middleware and dependencies.

This module provides API key authentication for protected endpoints.
"""

import hashlib
from typing import Callable, FrozenSet, List, Optional, Set

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader

logger = structlog.get_logger(__name__)

# Header name for API key
API_KEY_HEADER_NAME = "X-API-Key"

# FastAPI security scheme for OpenAPI docs
api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)


def hash_api_key(api_key: str) -> str:
    """
    Create a safe hash of an API key for logging.

    Args:
        api_key: The API key to hash

    Returns:
        SHA256 hash prefix (first 8 characters) for safe logging
    """
    if not api_key:
        return "empty"
    return hashlib.sha256(api_key.encode()).hexdigest()[:8]


class APIKeyAuth:
    """API key authentication handler.

    This class validates API keys against a configured list and can be used
    as a FastAPI dependency or for direct validation.
    """

    # Paths that don't require authentication
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
        api_keys: Optional[List[str]] = None,
        excluded_paths: Optional[Set[str]] = None,
    ):
        """
        Initialize API key authentication.

        Args:
            api_keys: List of valid API keys. Empty list allows all requests.
            excluded_paths: Paths that don't require authentication.
        """
        self._api_keys: Set[str] = set(api_keys) if api_keys else set()
        self._excluded_paths = excluded_paths or self.DEFAULT_EXCLUDED_PATHS
        self._allow_all = len(self._api_keys) == 0

        if self._allow_all:
            logger.warning(
                "No API keys configured, authentication is disabled",
                component="auth",
            )
        else:
            logger.info(
                "API key authentication initialized",
                num_keys=len(self._api_keys),
                excluded_paths=list(self._excluded_paths),
            )

    @property
    def api_keys(self) -> Set[str]:
        """Get the set of valid API keys."""
        return self._api_keys

    @property
    def excluded_paths(self) -> Set[str]:
        """Get the set of excluded paths."""
        return set(self._excluded_paths)

    @property
    def allow_all(self) -> bool:
        """Check if authentication is disabled."""
        return self._allow_all

    def is_path_excluded(self, path: str) -> bool:
        """
        Check if a path is excluded from authentication.

        Args:
            path: Request path to check

        Returns:
            True if path is excluded, False otherwise
        """
        # Normalize path
        path = path.rstrip("/")
        if not path:
            path = "/"

        # Check for exact match or prefix match (e.g. /docs matching /docs/subpath).
        # This is safer to avoid partial matches (e.g. /admin matching /admin_secret).
        for excluded in self._excluded_paths:
            if path == excluded or path.startswith(excluded + "/"):
                return True
        return False

    def validate_api_key(self, api_key: Optional[str]) -> bool:
        """
        Validate an API key.

        Args:
            api_key: The API key to validate

        Returns:
            True if valid, False otherwise
        """
        if self._allow_all:
            return True

        if not api_key:
            return False

        return api_key in self._api_keys

    def authenticate(self, request: Request, api_key: Optional[str]) -> bool:
        """
        Authenticate a request.

        Args:
            request: The FastAPI request
            api_key: The API key from header

        Returns:
            True if authenticated, False otherwise

        Raises:
            HTTPException: If authentication fails
        """
        path = request.url.path

        # Check if path is excluded
        if self.is_path_excluded(path):
            logger.debug(
                "Path excluded from authentication",
                path=path,
            )
            return True

        # Validate API key
        if self.validate_api_key(api_key):
            logger.debug(
                "API key authentication successful",
                path=path,
                key_hash=hash_api_key(api_key) if api_key else "none",
            )
            return True

        # Log failed authentication
        logger.warning(
            "API key authentication failed",
            path=path,
            key_hash=hash_api_key(api_key) if api_key else "none",
            client_ip=request.client.host if request.client else "unknown",
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )


# Global auth instance (configured at startup)
_auth_instance: Optional[APIKeyAuth] = None


def configure_auth(api_keys: Optional[List[str]] = None) -> APIKeyAuth:
    """
    Configure the global auth instance.

    Args:
        api_keys: List of valid API keys

    Returns:
        Configured APIKeyAuth instance
    """
    global _auth_instance
    _auth_instance = APIKeyAuth(api_keys=api_keys)
    return _auth_instance


def get_auth() -> APIKeyAuth:
    """
    Get the global auth instance.

    Returns:
        APIKeyAuth instance

    Raises:
        RuntimeError: If auth not configured
    """
    if _auth_instance is None:
        # Return a default instance if not configured
        return APIKeyAuth()
    return _auth_instance


async def get_api_key(
    request: Request,
    api_key: Optional[str] = Depends(api_key_header),  # noqa: B008
) -> Optional[str]:
    """Extract and validate API key from request.

    This dependency can be used on individual routes that require authentication.

    Args:
        request: The FastAPI request
        api_key: API key from header (injected by FastAPI)

    Returns:
        The validated API key

    Raises:
        HTTPException: If authentication fails
    """
    auth = get_auth()
    auth.authenticate(request, api_key)
    return api_key


def require_api_key(
    api_key: Optional[str] = Depends(get_api_key),  # noqa: B008
) -> str:
    """Require a valid API key for the route.

    Use this on routes that must have authentication.

    Args:
        api_key: The validated API key

    Returns:
        The API key

    Raises:
        HTTPException: If no API key provided
    """
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is required",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key


def create_auth_dependency(
    api_keys: List[str],
    excluded_paths: Optional[Set[str]] = None,
) -> Callable:
    """Create a custom auth dependency with specific keys.

    This is useful for creating isolated auth handlers for testing
    or for different API key sets.

    Args:
        api_keys: List of valid API keys
        excluded_paths: Paths to exclude from auth

    Returns:
        A FastAPI dependency function
    """
    auth = APIKeyAuth(api_keys=api_keys, excluded_paths=excluded_paths)

    async def dependency(
        request: Request,
        api_key: Optional[str] = Depends(api_key_header),  # noqa: B008
    ) -> Optional[str]:
        auth.authenticate(request, api_key)
        return api_key

    return dependency
