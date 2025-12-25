"""Cookie management service."""

import asyncio
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import structlog
from cachetools import TTLCache

from app.providers.exceptions import CookieError

logger = structlog.get_logger(__name__)


class CookieService:
    """Manages cookie files for video providers."""

    # Cookie file age warning threshold (7 days)
    WARNING_AGE_DAYS = 7

    # Cache TTL for validation results (1 hour)
    VALIDATION_CACHE_TTL = 3600

    # File modification check interval (60 seconds)
    FILE_CHECK_INTERVAL = 60

    def __init__(self, config: dict):
        """
        Initialize cookie service.

        Args:
            config: Configuration dictionary with provider cookie paths
        """
        self.config = config
        self.provider_cookies: Dict[str, str] = {}

        # Capture test mode at construction time (env var may not be visible in async context)
        self._test_mode = os.environ.get("APP_TESTING_TEST_MODE", "").lower() in (
            "true",
            "1",
            "yes",
        )
        if self._test_mode:
            logger.info("Cookie service initialized in test mode")

        # TTL cache for validation results (1 hour)
        self.validation_cache: TTLCache = TTLCache(maxsize=10, ttl=self.VALIDATION_CACHE_TTL)

        # Track file modification times
        self.file_mtimes: Dict[str, float] = {}

        # Track last file check time
        self.last_file_check: Dict[str, float] = {}

        self._load_provider_cookies()

    def _load_provider_cookies(self) -> None:
        """Load cookie paths for all configured providers."""
        providers_config = self.config.get("providers", {})

        for provider_name, provider_config in providers_config.items():
            if not provider_config.get("enabled", True):
                logger.info("Provider disabled, skipping cookie", provider=provider_name)
                continue

            cookie_path = provider_config.get("cookie_path")
            if cookie_path:
                self.provider_cookies[provider_name] = cookie_path
                logger.info(
                    "Cookie path registered",
                    provider=provider_name,
                    cookie_path=cookie_path,
                )

    def get_cookie_path(self, provider: str) -> Optional[str]:
        """
        Get cookie file path for a provider.

        Args:
            provider: Provider name (e.g., "youtube")

        Returns:
            Cookie file path, or None if not configured
        """
        return self.provider_cookies.get(provider)

    def load_cookie_file(self, provider: str) -> str:
        """
        Load cookie file content for a provider.

        Args:
            provider: Provider name

        Returns:
            Cookie file content

        Raises:
            CookieError: If cookie file is missing or cannot be read
        """
        cookie_path = self.get_cookie_path(provider)
        if not cookie_path:
            raise CookieError(f"No cookie path configured for provider: {provider}")

        path = Path(cookie_path)
        if not path.exists():
            raise CookieError(
                f"Cookie file not found for {provider}: {cookie_path}. "
                "Please export cookies from your browser and place them at this location."
            )

        try:
            content = path.read_text()
            logger.debug("Cookie file loaded", provider=provider, size=len(content))
            return content
        except Exception as e:
            raise CookieError(f"Failed to read cookie file for {provider}: {str(e)}") from e

    def validate_netscape_format(self, content: str, provider: str) -> bool:
        """
        Validate that cookie file is in Netscape format.

        Args:
            content: Cookie file content
            provider: Provider name (for logging)

        Returns:
            True if valid Netscape format

        Raises:
            CookieError: If format is invalid
        """
        lines = content.strip().split("\n")

        # Check for Netscape header
        if not content.strip():
            raise CookieError(f"Cookie file for {provider} is empty")

        # Netscape format should start with comment or have the header
        first_line = lines[0].strip()
        if first_line.startswith("# Netscape HTTP Cookie File") or first_line.startswith(
            "# HTTP Cookie File"
        ):
            logger.debug("Netscape format header found", provider=provider)
        else:
            # Some cookie files don't have the header but are still valid
            logger.debug("No Netscape header, checking cookie entries", provider=provider)

        # Validate cookie entries (skip comments and empty lines)
        valid_entries = 0
        for line in lines:
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Netscape format: domain, flag, path, secure, expiration, name, value
            parts = line.split("\t")
            if len(parts) != 7:
                raise CookieError(
                    f"Invalid cookie entry in {provider} cookie file. "
                    f"Expected 7 tab-separated fields, got {len(parts)}. "
                    "Ensure the file is in Netscape format."
                )

            valid_entries += 1

        if valid_entries == 0:
            raise CookieError(
                f"No valid cookie entries found in {provider} cookie file. "
                "The file may be corrupted or in the wrong format."
            )

        logger.info(
            "Cookie file validated",
            provider=provider,
            valid_entries=valid_entries,
        )
        return True

    def check_cookie_age(self, provider: str) -> Optional[str]:
        """
        Check cookie file age and return warning if too old.

        Args:
            provider: Provider name

        Returns:
            Warning message if cookie is old, None otherwise
        """
        cookie_path = self.get_cookie_path(provider)
        if not cookie_path:
            return None

        path = Path(cookie_path)
        if not path.exists():
            return None

        try:
            mtime = path.stat().st_mtime
            age = datetime.now() - datetime.fromtimestamp(mtime)
            age_days = age.days

            if age_days >= self.WARNING_AGE_DAYS:
                warning = (
                    f"Cookie file for {provider} is {age_days} days old. "
                    f"Consider refreshing cookies if authentication issues occur."
                )
                logger.warning(
                    "Cookie file is old",
                    provider=provider,
                    age_days=age_days,
                )
                return warning

            logger.debug("Cookie age check passed", provider=provider, age_days=age_days)
            return None

        except Exception as e:
            logger.error("Failed to check cookie age", provider=provider, error=str(e))
            return None

    def get_cookie_age_hours(self, provider: str) -> Optional[float]:
        """
        Get cookie file age in hours.

        Args:
            provider: Provider name

        Returns:
            Age in hours, or None if cannot be determined
        """
        cookie_path = self.get_cookie_path(provider)
        if not cookie_path:
            return None

        path = Path(cookie_path)
        if not path.exists():
            return None

        try:
            mtime = path.stat().st_mtime
            age_seconds = time.time() - mtime
            return age_seconds / 3600
        except Exception as e:
            logger.error("Failed to get cookie age", provider=provider, error=str(e))
            return None

    def validate_cookie_file(self, provider: str) -> None:
        """
        Validate cookie file for a provider.

        This performs format validation and age checking.

        Args:
            provider: Provider name

        Raises:
            CookieError: If validation fails
        """
        # Load and validate format
        content = self.load_cookie_file(provider)
        self.validate_netscape_format(content, provider)

        # Check age and log warning if needed
        warning = self.check_cookie_age(provider)
        if warning:
            logger.warning("Cookie age warning", provider=provider, warning=warning)

        logger.info("Cookie file validation complete", provider=provider)

    def list_providers_with_cookies(self) -> Dict[str, dict]:
        """
        List all providers with their cookie status.

        Returns:
            Dictionary mapping provider names to cookie status info
        """
        result = {}

        for provider, cookie_path in self.provider_cookies.items():
            path = Path(cookie_path)
            exists = path.exists()

            info = {
                "cookie_path": cookie_path,
                "exists": exists,
                "age_hours": self.get_cookie_age_hours(provider) if exists else None,
            }

            # Add warning if applicable
            if exists:
                warning = self.check_cookie_age(provider)
                if warning:
                    info["warning"] = warning

            result[provider] = info

        return result

    def _check_file_modification(self, provider: str) -> bool:
        """
        Check if cookie file has been modified since last check.

        Args:
            provider: Provider name

        Returns:
            True if file was modified, False otherwise
        """
        cookie_path = self.get_cookie_path(provider)
        if not cookie_path:
            return False

        path = Path(cookie_path)
        if not path.exists():
            return False

        try:
            current_mtime = path.stat().st_mtime
            last_mtime = self.file_mtimes.get(provider)

            if last_mtime is None or current_mtime != last_mtime:
                # File was modified
                self.file_mtimes[provider] = current_mtime
                logger.info(
                    "Cookie file modification detected",
                    provider=provider,
                    mtime=current_mtime,
                )
                return True

            return False

        except Exception as e:
            logger.error(
                "Failed to check file modification",
                provider=provider,
                error=str(e),
            )
            return False

    def _should_check_file(self, provider: str) -> bool:
        """
        Check if enough time has passed to check file modification.

        Args:
            provider: Provider name

        Returns:
            True if file should be checked
        """
        now = time.time()
        last_check = self.last_file_check.get(provider, 0)

        if now - last_check >= self.FILE_CHECK_INTERVAL:
            self.last_file_check[provider] = now
            return True

        return False

    def _invalidate_cache(self, provider: str) -> None:
        """
        Invalidate validation cache for a provider.

        Args:
            provider: Provider name
        """
        if provider in self.validation_cache:
            del self.validation_cache[provider]
            logger.info("Validation cache invalidated", provider=provider)

    async def validate_cookie(self, provider: str) -> bool:
        """
        Validate cookie with caching and YouTube authentication test.

        This method:
        1. Checks if file was modified (every 60 seconds)
        2. Invalidates cache if file was modified
        3. Returns cached result if available
        4. Otherwise performs full validation including YouTube test

        Args:
            provider: Provider name

        Returns:
            True if cookie is valid

        Raises:
            CookieError: If validation fails
        """
        # Check if we should check file modification
        if self._should_check_file(provider) and self._check_file_modification(provider):
            # File was modified, invalidate cache
            self._invalidate_cache(provider)

        # Check cache
        if provider in self.validation_cache:
            cached_result: bool = self.validation_cache[provider]
            logger.debug(
                "Cookie validation from cache",
                provider=provider,
                is_valid=cached_result,
            )
            return cached_result

        # Perform full validation
        logger.info("Performing full cookie validation", provider=provider)

        try:
            # Basic file validation
            self.validate_cookie_file(provider)

            # YouTube-specific authentication test
            validation_result: bool
            if provider == "youtube":
                validation_result = await self._test_youtube_authentication()
            else:
                # For other providers, basic validation is enough
                validation_result = True

            # Cache the result
            self.validation_cache[provider] = validation_result

            logger.info(
                "Cookie validation complete",
                provider=provider,
                is_valid=validation_result,
            )

            return validation_result

        except CookieError:
            # Don't cache failures - always re-validate on error
            # This ensures consistent behavior (always raises on failure)
            # and allows users to fix issues and retry immediately
            raise

    async def _test_youtube_authentication(self) -> bool:
        """
        Test YouTube authentication with a real request.

        Returns:
            True if authentication succeeds

        Raises:
            CookieError: If authentication fails
        """
        # Skip validation in test mode (yt-dlp is mocked)
        if self._test_mode:
            logger.debug("Skipping YouTube authentication test (test mode)")
            return True

        cookie_path = self.get_cookie_path("youtube")
        if not cookie_path:
            raise CookieError("No cookie path configured for YouTube")

        logger.debug("Testing YouTube authentication")

        try:
            # Use a known public video to test authentication
            # This video is "Me at the zoo" - first YouTube video
            test_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"

            # Run yt-dlp with --simulate to test without downloading
            # nosec B603: subprocess call with validated inputs
            process = await asyncio.create_subprocess_exec(
                "yt-dlp",
                "--cookies",
                cookie_path,
                "--simulate",
                "--no-warnings",
                "--quiet",
                test_url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10.0)

            if process.returncode == 0:
                logger.info("YouTube authentication test passed")
                return True
            else:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(
                    "YouTube authentication test failed",
                    returncode=process.returncode,
                    error=error_msg,
                )
                raise CookieError(
                    f"YouTube authentication failed. The cookie may be expired or invalid. "
                    f"Please export fresh cookies from your browser. Error: {error_msg}"
                )

        except asyncio.TimeoutError:
            logger.error("YouTube authentication test timed out")
            raise CookieError(
                "YouTube authentication test timed out. Check your network connection."
            )
        except FileNotFoundError:
            logger.error("yt-dlp not found")
            raise CookieError(
                "yt-dlp is not installed or not in PATH. Cannot validate YouTube cookies."
            )
        except Exception as e:
            logger.error("YouTube authentication test error", error=str(e), exc_info=True)
            raise CookieError(f"Failed to test YouTube authentication: {str(e)}") from e

    def get_validation_cache_status(self) -> Dict[str, dict]:
        """
        Get current validation cache status.

        Returns:
            Dictionary with cache information for each provider
        """
        result = {}

        for provider in self.provider_cookies.keys():
            cached = provider in self.validation_cache
            result[provider] = {
                "cached": cached,
                "is_valid": self.validation_cache.get(provider) if cached else None,
                "last_file_check": self.last_file_check.get(provider),
                "file_mtime": self.file_mtimes.get(provider),
            }

        return result

    async def reload_cookie(self, provider: str) -> dict:
        """
        Reload cookie file for a provider with validation.

        This method:
        1. Saves the current validation state
        2. Invalidates the cache
        3. Validates the new cookie file
        4. Rolls back if validation fails

        Args:
            provider: Provider name

        Returns:
            Dictionary with reload result

        Raises:
            CookieError: If provider not found or reload fails
        """
        if provider not in self.provider_cookies:
            raise CookieError(f"Provider '{provider}' not configured")

        logger.info("Starting cookie reload", provider=provider)

        # Save previous validation state for potential rollback
        previous_valid = self.validation_cache.get(provider)
        previous_mtime = self.file_mtimes.get(provider)

        try:
            # Invalidate cache to force revalidation
            self._invalidate_cache(provider)

            # Force file modification check
            self.last_file_check[provider] = 0

            # Validate the new cookie
            is_valid = await self.validate_cookie(provider)

            if not is_valid:
                raise CookieError(f"New cookie for {provider} failed validation")

            logger.info(
                "Cookie reload successful",
                provider=provider,
            )

            return {
                "success": True,
                "provider": provider,
                "message": f"Cookie for {provider} reloaded and validated successfully",
                "age_hours": self.get_cookie_age_hours(provider),
            }

        except Exception as e:
            # Rollback: restore previous cache state
            logger.error(
                "Cookie reload failed, rolling back",
                provider=provider,
                error=str(e),
            )

            if previous_valid is not None:
                self.validation_cache[provider] = previous_valid
                logger.info("Rolled back to previous validation state", provider=provider)

            if previous_mtime is not None:
                self.file_mtimes[provider] = previous_mtime

            raise CookieError(
                f"Failed to reload cookie for {provider}: {str(e)}. "
                "Previous cookie state has been retained."
            ) from e
