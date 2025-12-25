"""Startup validation for the application.

This module provides startup checks for external dependencies and
configuration validation to ensure the system is properly initialized
before accepting requests.

Implements requirements:
- Req 10: JavaScript Challenge Resolution (Node.js >= 20)
- Req 21: Node.js Runtime Configuration (--js-runtimes flag)
- Req 22: Output Directory Management
- Req 23: Cookie Directory Management
- Req 47: Graceful Startup Mode (degraded mode support)
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from app.core.checks import check_ffmpeg, check_nodejs, check_ytdlp
from app.core.config import Config

logger = structlog.get_logger(__name__)


@dataclass
class ComponentCheckResult:
    """Result of a startup component check.

    Attributes:
        name: Component name (e.g., "ytdlp", "ffmpeg", "nodejs")
        passed: Whether the check passed
        critical: If True, failure blocks startup (unless degraded mode)
        version: Version string if available
        message: Human-readable message about the result
        details: Additional details about the check
    """

    name: str
    passed: bool
    critical: bool
    version: Optional[str] = None
    message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StartupResult:
    """Result of full startup validation.

    Attributes:
        success: Whether startup can proceed
        degraded_mode: Whether the application is running in degraded mode
        checks: List of individual component check results
        disabled_providers: List of provider names that were disabled
        errors: List of error messages for critical failures
        warnings: List of warning messages for non-critical issues
    """

    success: bool
    degraded_mode: bool
    checks: List[ComponentCheckResult] = field(default_factory=list)
    disabled_providers: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class StartupValidator:
    """Validates system components at startup.

    This class performs comprehensive startup validation:
    - External binaries: yt-dlp, ffmpeg, Node.js >= 20
    - Storage: output directory creation and write permissions
    - Cookies: file existence and format validation
    - yt-dlp configuration: Node.js runtime setup

    Supports degraded mode where the application can start with
    warnings when optional components are unavailable.
    """

    # Minimum Node.js version required for JavaScript challenge resolution
    MIN_NODEJS_VERSION = 20

    # Components that must be available even in degraded mode
    ALWAYS_CRITICAL_COMPONENTS = {"ytdlp", "storage"}

    def __init__(self, config: Config):
        """Initialize the startup validator.

        Args:
            config: Application configuration.
        """
        self.config = config
        self.allow_degraded = config.security.allow_degraded_start
        self.results: List[ComponentCheckResult] = []
        self.disabled_providers: List[str] = []
        self.errors: List[str] = []
        self.warnings: List[str] = []

    async def validate_all(self) -> StartupResult:
        """Run all startup validations.

        Returns:
            StartupResult with overall status and component details.
        """
        logger.info(
            "startup_validation_started",
            allow_degraded_start=self.allow_degraded,
        )

        # Reset state for fresh validation
        self.results = []
        self.disabled_providers = []
        self.errors = []
        self.warnings = []

        # Run all checks
        await self._run_checks()

        # Determine overall status
        critical_failures = [r for r in self.results if not r.passed and r.critical]
        non_critical_failures = [r for r in self.results if not r.passed and not r.critical]

        # Configure yt-dlp runtime if Node.js is available
        nodejs_check = next((r for r in self.results if r.name == "nodejs"), None)
        if nodejs_check and nodejs_check.passed:
            self.configure_ytdlp_runtime()

        # Determine if we can start
        if critical_failures:
            if self.allow_degraded:
                # In degraded mode, only truly critical failures block startup
                truly_critical = [
                    r for r in critical_failures if r.name in self.ALWAYS_CRITICAL_COMPONENTS
                ]
                if truly_critical:
                    for r in truly_critical:
                        self.errors.append(f"{r.name}: {r.message}")
                    success = False
                    degraded_mode = False
                else:
                    # Other critical failures become warnings in degraded mode
                    for r in critical_failures:
                        self.warnings.append(f"{r.name}: {r.message}")
                    success = True
                    degraded_mode = True
            else:
                for r in critical_failures:
                    self.errors.append(f"{r.name}: {r.message}")
                success = False
                degraded_mode = False
        else:
            success = True
            degraded_mode = len(non_critical_failures) > 0 and self.allow_degraded

        # Add non-critical failures as warnings
        for r in non_critical_failures:
            self.warnings.append(f"{r.name}: {r.message}")

        result = StartupResult(
            success=success,
            degraded_mode=degraded_mode,
            checks=self.results,
            disabled_providers=self.disabled_providers,
            errors=self.errors,
            warnings=self.warnings,
        )

        log_method = logger.info if success else logger.error
        log_method(
            "startup_validation_completed",
            success=success,
            degraded_mode=degraded_mode,
            disabled_providers=self.disabled_providers,
            error_count=len(self.errors),
            warning_count=len(self.warnings),
        )

        return result

    async def _run_checks(self) -> None:
        """Run all component checks."""
        # Check external binaries (critical)
        ytdlp_result = await self.check_ytdlp()
        self.results.append(ytdlp_result)

        ffmpeg_result = await self.check_ffmpeg()
        self.results.append(ffmpeg_result)

        nodejs_result = await self.check_nodejs()
        self.results.append(nodejs_result)

        # Check storage (critical)
        storage_result = await self.check_storage()
        self.results.append(storage_result)

        # Check cookies (non-critical in degraded mode)
        cookie_result = await self.check_cookies()
        self.results.append(cookie_result)

    async def check_ytdlp(self) -> ComponentCheckResult:
        """Check yt-dlp availability and version.

        This is a CRITICAL check - startup fails if yt-dlp is not available.

        Returns:
            ComponentCheckResult with yt-dlp status.
        """
        result = await check_ytdlp()

        if result.available:
            logger.info("ytdlp_check_passed", version=result.version)
            return ComponentCheckResult(
                name="ytdlp",
                passed=True,
                critical=True,
                version=result.version,
                message="yt-dlp is available",
            )

        logger.error("ytdlp_check_failed", error=result.error)
        return ComponentCheckResult(
            name="ytdlp",
            passed=False,
            critical=True,
            message=result.error or "yt-dlp is not available",
        )

    async def check_ffmpeg(self) -> ComponentCheckResult:
        """Check ffmpeg availability and version.

        This is a CRITICAL check - startup fails if ffmpeg is not available.

        Returns:
            ComponentCheckResult with ffmpeg status.
        """
        result = await check_ffmpeg()

        if result.available:
            logger.info("ffmpeg_check_passed", version=result.version)
            return ComponentCheckResult(
                name="ffmpeg",
                passed=True,
                critical=True,
                version=result.version,
                message="ffmpeg is available",
            )

        logger.error("ffmpeg_check_failed", error=result.error)
        return ComponentCheckResult(
            name="ffmpeg",
            passed=False,
            critical=True,
            message=result.error or "ffmpeg is not available",
        )

    async def check_nodejs(self) -> ComponentCheckResult:
        """Check Node.js availability and version >= 20.

        This is a CRITICAL check - Node.js >= 20 is required for
        JavaScript challenge resolution (Req 10).

        Returns:
            ComponentCheckResult with Node.js status.
        """
        result = await check_nodejs(min_version=self.MIN_NODEJS_VERSION)

        if result.available:
            logger.info("nodejs_check_passed", version=result.version)
            return ComponentCheckResult(
                name="nodejs",
                passed=True,
                critical=True,
                version=result.version,
                message="Node.js is available",
            )

        logger.error("nodejs_check_failed", error=result.error)
        return ComponentCheckResult(
            name="nodejs",
            passed=False,
            critical=True,
            message=result.error or f"Node.js >= {self.MIN_NODEJS_VERSION} is required",
        )

    async def check_storage(self) -> ComponentCheckResult:
        """Check storage directory availability and permissions.

        This is a CRITICAL check - startup fails if storage is not writable.
        Creates the output directory if it doesn't exist.

        Returns:
            ComponentCheckResult with storage status.
        """
        output_dir = Path(self.config.storage.output_dir)

        try:
            # Create directory if it doesn't exist
            if not output_dir.exists():
                output_dir.mkdir(parents=True, exist_ok=True)
                logger.info("output_directory_created", path=str(output_dir))

            # Test write permissions
            test_file = output_dir / f".write_test_{os.getpid()}"
            try:
                test_file.touch()
                test_file.unlink(missing_ok=True)
            except PermissionError:
                logger.error(
                    "storage_permission_error",
                    path=str(output_dir),
                )
                return ComponentCheckResult(
                    name="storage",
                    passed=False,
                    critical=True,
                    message=f"Cannot write to output directory: {output_dir}",
                )

            logger.info("storage_check_passed", path=str(output_dir))
            return ComponentCheckResult(
                name="storage",
                passed=True,
                critical=True,
                message="Storage is available and writable",
                details={"output_dir": str(output_dir)},
            )

        except OSError as e:
            logger.error("storage_check_failed", path=str(output_dir), error=str(e))
            return ComponentCheckResult(
                name="storage",
                passed=False,
                critical=True,
                message=f"Storage check failed: {e}",
            )

    def _cookie_failure(self, message: str, provider: str = "youtube") -> ComponentCheckResult:
        """Create a cookie check failure result.

        Args:
            message: Error message describing the failure.
            provider: Provider name to disable in degraded mode.

        Returns:
            ComponentCheckResult with appropriate critical flag based on mode.
        """
        if self.allow_degraded:
            self.disabled_providers.append(provider)
            return ComponentCheckResult(
                name="cookies",
                passed=False,
                critical=False,
                message=message,
            )
        return ComponentCheckResult(
            name="cookies",
            passed=False,
            critical=True,
            message=message,
        )

    async def check_cookies(self) -> ComponentCheckResult:
        """Check cookie file availability and format.

        This is a NON-CRITICAL check in degraded mode - if cookies are
        missing, the provider is disabled but startup continues.

        Returns:
            ComponentCheckResult with cookie status.
        """
        # Check YouTube provider cookie if enabled
        if not self.config.providers.youtube.enabled:
            logger.info("youtube_provider_disabled")
            return ComponentCheckResult(
                name="cookies",
                passed=True,
                critical=False,
                message="YouTube provider is disabled, no cookie check needed",
            )

        cookie_path = self.config.providers.youtube.cookie_path
        if not cookie_path:
            logger.warning("youtube_cookie_not_configured")
            return self._cookie_failure("No cookie path configured for YouTube")

        path = Path(cookie_path)

        # Check if file exists
        if not path.exists():
            logger.warning("youtube_cookie_not_found", path=cookie_path)
            return self._cookie_failure(f"Cookie file not found: {cookie_path}")

        # Check if file is readable and valid
        try:
            content = path.read_text()
            if not content.strip():
                logger.warning("youtube_cookie_empty", path=cookie_path)
                return self._cookie_failure("Cookie file is empty")

            # Basic Netscape format validation
            lines = [
                ln for ln in content.strip().split("\n") if ln.strip() and not ln.startswith("#")
            ]
            valid_entries = sum(1 for line in lines if len(line.split("\t")) == 7)

            if valid_entries == 0:
                logger.warning("youtube_cookie_invalid_format", path=cookie_path)
                return self._cookie_failure(
                    "Cookie file has invalid format (no valid Netscape entries)"
                )

            logger.info(
                "cookies_check_passed",
                path=cookie_path,
                valid_entries=valid_entries,
            )
            return ComponentCheckResult(
                name="cookies",
                passed=True,
                critical=False,
                message="Cookie file is valid",
                details={"path": cookie_path, "valid_entries": valid_entries},
            )

        except PermissionError:
            logger.error("youtube_cookie_permission_error", path=cookie_path)
            return self._cookie_failure(f"Cannot read cookie file: {cookie_path}")
        except Exception as e:
            logger.error("youtube_cookie_read_error", path=cookie_path, error=str(e))
            return self._cookie_failure(f"Error reading cookie file: {e}")

    def configure_ytdlp_runtime(self) -> None:
        """Configure yt-dlp to use Node.js runtime for JavaScript challenges.

        Creates or updates the yt-dlp configuration file to include
        the --js-runtimes node flag (Req 21).
        """
        # Determine config file location
        xdg_config = os.environ.get("XDG_CONFIG_HOME", "")
        if xdg_config:
            config_dir = Path(xdg_config) / "yt-dlp"
        else:
            config_dir = Path.home() / ".config" / "yt-dlp"

        config_file = config_dir / "config"

        try:
            # Create directory if it doesn't exist
            config_dir.mkdir(parents=True, exist_ok=True)

            # Read existing config
            existing_content = ""
            if config_file.exists():
                existing_content = config_file.read_text()

            # Check if --js-runtimes is already configured
            if "--js-runtimes" in existing_content:
                logger.debug(
                    "ytdlp_config_already_set",
                    config_file=str(config_file),
                )
                return

            # Append the configuration
            with config_file.open("a") as f:
                if existing_content and not existing_content.endswith("\n"):
                    f.write("\n")
                f.write("# Added by yt-dlp-api for JavaScript challenge resolution\n")
                f.write("--js-runtimes node\n")

            logger.info(
                "ytdlp_runtime_configured",
                config_file=str(config_file),
            )

        except Exception as e:
            # Log warning but don't fail - the provider can still pass the flag manually
            logger.warning(
                "ytdlp_config_write_failed",
                config_file=str(config_file),
                error=str(e),
            )
