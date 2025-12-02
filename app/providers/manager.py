"""Provider manager for registration and selection."""

from typing import Any, Callable, Dict, Optional

import structlog

from app.providers.base import VideoProvider
from app.providers.exceptions import InvalidURLError, ProviderError

logger = structlog.get_logger(__name__)


class ProviderManager:
    """Manages video provider registration and selection."""

    def __init__(self) -> None:
        """Initialize the provider manager."""
        self._providers: Dict[str, VideoProvider] = {}
        self._enabled_providers: Dict[str, bool] = {}

    def register_provider(self, name: str, provider: VideoProvider, enabled: bool = True) -> None:
        """
        Register a video provider.

        Args:
            name: Provider name (e.g., "youtube")
            provider: Provider instance
            enabled: Whether provider is enabled
        """
        self._providers[name] = provider
        self._enabled_providers[name] = enabled

        logger.info("Provider registered", provider=name, enabled=enabled)

    def enable_provider(self, name: str) -> None:
        """
        Enable a registered provider.

        Args:
            name: Provider name

        Raises:
            ValueError: If provider is not registered
        """
        if name not in self._providers:
            raise ValueError(f"Provider '{name}' is not registered")

        self._enabled_providers[name] = True
        logger.info("Provider enabled", provider=name)

    def disable_provider(self, name: str) -> None:
        """
        Disable a registered provider.

        Args:
            name: Provider name

        Raises:
            ValueError: If provider is not registered
        """
        if name not in self._providers:
            raise ValueError(f"Provider '{name}' is not registered")

        self._enabled_providers[name] = False
        logger.info("Provider disabled", provider=name)

    def is_provider_enabled(self, name: str) -> bool:
        """
        Check if a provider is enabled.

        Args:
            name: Provider name

        Returns:
            True if provider is enabled, False otherwise
        """
        return self._enabled_providers.get(name, False)

    def get_provider_for_url(self, url: str) -> VideoProvider:
        """
        Select appropriate provider based on URL.

        Args:
            url: Video URL

        Returns:
            Provider instance that can handle the URL

        Raises:
            InvalidURLError: If no provider can handle the URL
        """
        for name, provider in self._providers.items():  # pragma: no cover
            # Skip disabled providers
            if not self._enabled_providers.get(name, False):
                continue

            try:
                if provider.validate_url(url):
                    logger.debug("Provider selected for URL", provider=name, url=url)
                    return provider
            except Exception as e:
                # Isolate provider errors - don't let one provider's
                # validation error prevent checking other providers
                logger.warning("Provider validation error", provider=name, url=url, error=str(e))
                continue

        # No provider found
        raise InvalidURLError(
            f"No provider available for URL: {url}. "
            "Ensure the URL is from a supported platform and the provider is enabled."
        )

    def get_provider_by_name(self, name: str) -> Optional[VideoProvider]:
        """
        Get a provider by name.

        Args:
            name: Provider name

        Returns:
            Provider instance, or None if not found
        """
        return self._providers.get(name)

    def list_providers(self) -> Dict[str, bool]:
        """
        List all registered providers and their status.

        Returns:
            Dictionary mapping provider names to enabled status
        """
        return {name: self._enabled_providers.get(name, False) for name in self._providers.keys()}

    async def execute_with_error_isolation(
        self, provider_name: str, operation: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        """
        Execute a provider operation with error isolation.

        This ensures that errors from one provider don't crash the entire system.

        Args:
            provider_name: Name of the provider
            operation: Async callable to execute
            *args: Positional arguments for operation
            **kwargs: Keyword arguments for operation

        Returns:
            Result of the operation

        Raises:
            ProviderError: If operation fails
        """
        try:  # pragma: no cover
            logger.debug(
                "Executing provider operation", provider=provider_name, operation=operation.__name__
            )

            result = await operation(*args, **kwargs)

            logger.debug(
                "Provider operation completed", provider=provider_name, operation=operation.__name__
            )

            return result

        except ProviderError:
            # Re-raise provider errors as-is
            raise

        except Exception as e:
            # Wrap unexpected errors
            logger.error(
                "Provider operation failed with unexpected error",
                provider=provider_name,
                operation=operation.__name__,
                error=str(e),
                exc_info=True,
            )
            raise ProviderError(
                f"Provider '{provider_name}' encountered an unexpected error: {str(e)}"
            ) from e
