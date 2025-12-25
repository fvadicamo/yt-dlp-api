"""Tests for startup validation.

This module tests the startup validation system including:
- Component availability checks (yt-dlp, ffmpeg, Node.js)
- Storage directory validation
- Cookie file validation
- Degraded mode behavior
- yt-dlp runtime configuration
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.checks import CheckResult, check_ffmpeg, check_nodejs, check_ytdlp
from app.core.config import (
    Config,
    ProvidersConfig,
    SecurityConfig,
    StorageConfig,
    YouTubeProviderConfig,
)
from app.core.startup import ComponentCheckResult, StartupResult, StartupValidator

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    """Create a temporary output directory."""
    output_dir = tmp_path / "downloads"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def tmp_cookie_file(tmp_path: Path) -> Path:
    """Create a valid temporary cookie file."""
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text(
        "# Netscape HTTP Cookie File\n" ".youtube.com\tTRUE\t/\tTRUE\t1234567890\tname\tvalue\n"
    )
    return cookie_file


@pytest.fixture
def config(tmp_output_dir: Path, tmp_cookie_file: Path) -> Config:
    """Create a test configuration."""
    return Config(
        security=SecurityConfig(
            api_keys=["test-key"],
            allow_degraded_start=False,
        ),
        storage=StorageConfig(output_dir=str(tmp_output_dir)),
        providers=ProvidersConfig(
            youtube=YouTubeProviderConfig(
                enabled=True,
                cookie_path=str(tmp_cookie_file),
            )
        ),
    )


@pytest.fixture
def config_degraded(tmp_output_dir: Path, tmp_cookie_file: Path) -> Config:
    """Create a test configuration with degraded mode enabled."""
    return Config(
        security=SecurityConfig(
            api_keys=["test-key"],
            allow_degraded_start=True,
        ),
        storage=StorageConfig(output_dir=str(tmp_output_dir)),
        providers=ProvidersConfig(
            youtube=YouTubeProviderConfig(
                enabled=True,
                cookie_path=str(tmp_cookie_file),
            )
        ),
    )


@pytest.fixture
def validator(config: Config) -> StartupValidator:
    """Create a StartupValidator instance."""
    return StartupValidator(config)


@pytest.fixture
def validator_degraded(config_degraded: Config) -> StartupValidator:
    """Create a StartupValidator instance with degraded mode."""
    return StartupValidator(config_degraded)


# =============================================================================
# Tests for shared check utilities (app/core/checks.py)
# =============================================================================


class TestCheckYtdlp:
    """Tests for check_ytdlp function."""

    @pytest.mark.asyncio
    async def test_ytdlp_available(self) -> None:
        """Test yt-dlp check when available."""
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(b"2024.01.15", b""))
            mock_subprocess.return_value = mock_proc

            result = await check_ytdlp()

            assert result.available is True
            assert result.version == "2024.01.15"
            assert result.error is None

    @pytest.mark.asyncio
    async def test_ytdlp_not_found(self) -> None:
        """Test yt-dlp check when not installed."""
        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError(),
        ):
            result = await check_ytdlp()

            assert result.available is False
            assert result.error == "yt-dlp not found"

    @pytest.mark.asyncio
    async def test_ytdlp_timeout(self) -> None:
        """Test yt-dlp check timeout handling."""
        import asyncio

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
            mock_proc.kill = MagicMock()
            mock_proc.wait = AsyncMock()
            mock_subprocess.return_value = mock_proc

            result = await check_ytdlp(timeout=0.1)

            assert result.available is False
            assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_ytdlp_non_zero_exit(self) -> None:
        """Test yt-dlp check with non-zero exit code."""
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_proc = AsyncMock()
            mock_proc.returncode = 1
            mock_proc.communicate = AsyncMock(return_value=(b"", b"error"))
            mock_subprocess.return_value = mock_proc

            result = await check_ytdlp()

            assert result.available is False
            assert "non-zero" in result.error.lower()


class TestCheckFfmpeg:
    """Tests for check_ffmpeg function."""

    @pytest.mark.asyncio
    async def test_ffmpeg_available(self) -> None:
        """Test ffmpeg check when available."""
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(b"ffmpeg version 6.0 Copyright", b""))
            mock_subprocess.return_value = mock_proc

            result = await check_ffmpeg()

            assert result.available is True
            assert result.version == "6.0"
            assert result.error is None

    @pytest.mark.asyncio
    async def test_ffmpeg_not_found(self) -> None:
        """Test ffmpeg check when not installed."""
        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError(),
        ):
            result = await check_ffmpeg()

            assert result.available is False
            assert result.error == "ffmpeg not found"

    @pytest.mark.asyncio
    async def test_ffmpeg_version_unknown(self) -> None:
        """Test ffmpeg check with unparseable version."""
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(b"some output", b""))
            mock_subprocess.return_value = mock_proc

            result = await check_ffmpeg()

            assert result.available is True
            assert result.version == "unknown"


class TestCheckNodejs:
    """Tests for check_nodejs function."""

    @pytest.mark.asyncio
    async def test_nodejs_version_valid(self) -> None:
        """Test Node.js check with valid version >= 20."""
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(b"v20.10.0", b""))
            mock_subprocess.return_value = mock_proc

            result = await check_nodejs(min_version=20)

            assert result.available is True
            assert result.version == "v20.10.0"
            assert result.error is None

    @pytest.mark.asyncio
    async def test_nodejs_version_too_old(self) -> None:
        """Test Node.js check with version < 20."""
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(b"v18.0.0", b""))
            mock_subprocess.return_value = mock_proc

            result = await check_nodejs(min_version=20)

            assert result.available is False
            assert result.version == "v18.0.0"
            assert "20" in result.error
            assert "18" in result.error

    @pytest.mark.asyncio
    async def test_nodejs_not_found(self) -> None:
        """Test Node.js check when not installed."""
        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError(),
        ):
            result = await check_nodejs()

            assert result.available is False
            assert result.error == "node not found"

    @pytest.mark.asyncio
    async def test_nodejs_version_22(self) -> None:
        """Test Node.js check with version 22."""
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(b"v22.5.1", b""))
            mock_subprocess.return_value = mock_proc

            result = await check_nodejs(min_version=20)

            assert result.available is True
            assert result.version == "v22.5.1"


# =============================================================================
# Tests for StartupValidator component checks
# =============================================================================


class TestStartupValidatorChecks:
    """Tests for individual StartupValidator check methods."""

    @pytest.mark.asyncio
    async def test_check_ytdlp_passed(self, validator: StartupValidator) -> None:
        """Test check_ytdlp when available."""
        with patch("app.core.startup.check_ytdlp") as mock_check:
            mock_check.return_value = CheckResult(
                name="ytdlp", available=True, version="2024.01.15"
            )

            result = await validator.check_ytdlp()

            assert result.passed is True
            assert result.critical is True
            assert result.version == "2024.01.15"

    @pytest.mark.asyncio
    async def test_check_ytdlp_failed(self, validator: StartupValidator) -> None:
        """Test check_ytdlp when not available."""
        with patch("app.core.startup.check_ytdlp") as mock_check:
            mock_check.return_value = CheckResult(
                name="ytdlp", available=False, error="yt-dlp not found"
            )

            result = await validator.check_ytdlp()

            assert result.passed is False
            assert result.critical is True
            assert "not found" in result.message.lower()

    @pytest.mark.asyncio
    async def test_check_ffmpeg_passed(self, validator: StartupValidator) -> None:
        """Test check_ffmpeg when available."""
        with patch("app.core.startup.check_ffmpeg") as mock_check:
            mock_check.return_value = CheckResult(name="ffmpeg", available=True, version="6.0")

            result = await validator.check_ffmpeg()

            assert result.passed is True
            assert result.critical is True

    @pytest.mark.asyncio
    async def test_check_nodejs_passed(self, validator: StartupValidator) -> None:
        """Test check_nodejs when available with valid version."""
        with patch("app.core.startup.check_nodejs") as mock_check:
            mock_check.return_value = CheckResult(name="nodejs", available=True, version="v20.10.0")

            result = await validator.check_nodejs()

            assert result.passed is True
            assert result.critical is True
            assert result.version == "v20.10.0"

    @pytest.mark.asyncio
    async def test_check_nodejs_version_too_old(self, validator: StartupValidator) -> None:
        """Test check_nodejs with version below minimum."""
        with patch("app.core.startup.check_nodejs") as mock_check:
            mock_check.return_value = CheckResult(
                name="nodejs",
                available=False,
                version="v18.0.0",
                error="Node.js >= 20 required, found v18.0.0",
            )

            result = await validator.check_nodejs()

            assert result.passed is False
            assert result.critical is True
            assert "20" in result.message


class TestStorageValidation:
    """Tests for storage directory validation."""

    @pytest.mark.asyncio
    async def test_storage_check_passed(
        self, validator: StartupValidator, tmp_output_dir: Path
    ) -> None:
        """Test storage check with valid writable directory."""
        result = await validator.check_storage()

        assert result.passed is True
        assert result.critical is True
        assert "writable" in result.message.lower()

    @pytest.mark.asyncio
    async def test_storage_creates_directory(self, tmp_path: Path) -> None:
        """Test storage check creates directory if not exists."""
        output_dir = tmp_path / "new_downloads"
        assert not output_dir.exists()

        config = Config(
            security=SecurityConfig(api_keys=["test"]),
            storage=StorageConfig(output_dir=str(output_dir)),
        )
        validator = StartupValidator(config)

        result = await validator.check_storage()

        assert result.passed is True
        assert output_dir.exists()

    @pytest.mark.asyncio
    async def test_storage_permission_error(self, tmp_path: Path) -> None:
        """Test storage check fails when directory is not writable."""
        output_dir = tmp_path / "downloads"
        output_dir.mkdir()

        config = Config(
            security=SecurityConfig(api_keys=["test"]),
            storage=StorageConfig(output_dir=str(output_dir)),
        )
        validator = StartupValidator(config)

        with patch.object(Path, "touch", side_effect=PermissionError()):
            result = await validator.check_storage()

            assert result.passed is False
            assert result.critical is True
            assert "cannot write" in result.message.lower()


class TestCookieValidation:
    """Tests for cookie file validation."""

    @pytest.mark.asyncio
    async def test_cookie_check_passed(
        self, validator: StartupValidator, tmp_cookie_file: Path
    ) -> None:
        """Test cookie check with valid cookie file."""
        result = await validator.check_cookies()

        assert result.passed is True
        assert result.critical is False

    @pytest.mark.asyncio
    async def test_cookie_file_not_found_strict(self, tmp_path: Path) -> None:
        """Test cookie check fails in strict mode when file not found."""
        config = Config(
            security=SecurityConfig(api_keys=["test"], allow_degraded_start=False),
            storage=StorageConfig(output_dir=str(tmp_path)),
            providers=ProvidersConfig(
                youtube=YouTubeProviderConfig(
                    enabled=True,
                    cookie_path=str(tmp_path / "missing.txt"),
                )
            ),
        )
        validator = StartupValidator(config)

        result = await validator.check_cookies()

        assert result.passed is False
        assert result.critical is True
        assert "not found" in result.message.lower()

    @pytest.mark.asyncio
    async def test_cookie_file_not_found_degraded(self, tmp_path: Path) -> None:
        """Test cookie check succeeds in degraded mode when file not found."""
        config = Config(
            security=SecurityConfig(api_keys=["test"], allow_degraded_start=True),
            storage=StorageConfig(output_dir=str(tmp_path)),
            providers=ProvidersConfig(
                youtube=YouTubeProviderConfig(
                    enabled=True,
                    cookie_path=str(tmp_path / "missing.txt"),
                )
            ),
        )
        validator = StartupValidator(config)

        result = await validator.check_cookies()

        assert result.passed is False
        assert result.critical is False  # Non-critical in degraded mode
        assert "youtube" in validator.disabled_providers

    @pytest.mark.asyncio
    async def test_cookie_file_empty(self, tmp_path: Path) -> None:
        """Test cookie check fails when file is empty."""
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("")

        config = Config(
            security=SecurityConfig(api_keys=["test"], allow_degraded_start=False),
            storage=StorageConfig(output_dir=str(tmp_path)),
            providers=ProvidersConfig(
                youtube=YouTubeProviderConfig(
                    enabled=True,
                    cookie_path=str(cookie_file),
                )
            ),
        )
        validator = StartupValidator(config)

        result = await validator.check_cookies()

        assert result.passed is False
        assert "empty" in result.message.lower()

    @pytest.mark.asyncio
    async def test_cookie_file_invalid_format(self, tmp_path: Path) -> None:
        """Test cookie check fails with invalid format."""
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("this is not a valid cookie file\n")

        config = Config(
            security=SecurityConfig(api_keys=["test"], allow_degraded_start=False),
            storage=StorageConfig(output_dir=str(tmp_path)),
            providers=ProvidersConfig(
                youtube=YouTubeProviderConfig(
                    enabled=True,
                    cookie_path=str(cookie_file),
                )
            ),
        )
        validator = StartupValidator(config)

        result = await validator.check_cookies()

        assert result.passed is False
        assert "invalid format" in result.message.lower()

    @pytest.mark.asyncio
    async def test_cookie_youtube_disabled(self, tmp_path: Path) -> None:
        """Test cookie check skipped when YouTube provider is disabled."""
        config = Config(
            security=SecurityConfig(api_keys=["test"]),
            storage=StorageConfig(output_dir=str(tmp_path)),
            providers=ProvidersConfig(youtube=YouTubeProviderConfig(enabled=False)),
        )
        validator = StartupValidator(config)

        result = await validator.check_cookies()

        assert result.passed is True
        assert "disabled" in result.message.lower()


# =============================================================================
# Tests for degraded mode behavior
# =============================================================================


class TestDegradedMode:
    """Tests for degraded mode behavior."""

    @pytest.mark.asyncio
    async def test_degraded_mode_allows_missing_cookie(self, tmp_path: Path) -> None:
        """Test degraded mode allows startup with missing cookie."""
        config = Config(
            security=SecurityConfig(api_keys=["test"], allow_degraded_start=True),
            storage=StorageConfig(output_dir=str(tmp_path)),
            providers=ProvidersConfig(
                youtube=YouTubeProviderConfig(
                    enabled=True,
                    cookie_path=str(tmp_path / "missing.txt"),
                )
            ),
        )

        validator = StartupValidator(config)

        # Mock binary checks to pass
        with (
            patch("app.core.startup.check_ytdlp") as mock_ytdlp,
            patch("app.core.startup.check_ffmpeg") as mock_ffmpeg,
            patch("app.core.startup.check_nodejs") as mock_nodejs,
            patch.object(validator, "configure_ytdlp_runtime"),
        ):
            mock_ytdlp.return_value = CheckResult("ytdlp", True, "2024.01.15")
            mock_ffmpeg.return_value = CheckResult("ffmpeg", True, "6.0")
            mock_nodejs.return_value = CheckResult("nodejs", True, "v20.10.0")

            result = await validator.validate_all()

            assert result.success is True
            assert result.degraded_mode is True
            assert "youtube" in result.disabled_providers
            assert len(result.warnings) > 0

    @pytest.mark.asyncio
    async def test_strict_mode_fails_on_missing_cookie(self, tmp_path: Path) -> None:
        """Test strict mode fails with missing cookie."""
        config = Config(
            security=SecurityConfig(api_keys=["test"], allow_degraded_start=False),
            storage=StorageConfig(output_dir=str(tmp_path)),
            providers=ProvidersConfig(
                youtube=YouTubeProviderConfig(
                    enabled=True,
                    cookie_path=str(tmp_path / "missing.txt"),
                )
            ),
        )

        validator = StartupValidator(config)

        # Mock binary checks to pass
        with (
            patch("app.core.startup.check_ytdlp") as mock_ytdlp,
            patch("app.core.startup.check_ffmpeg") as mock_ffmpeg,
            patch("app.core.startup.check_nodejs") as mock_nodejs,
        ):
            mock_ytdlp.return_value = CheckResult("ytdlp", True, "2024.01.15")
            mock_ffmpeg.return_value = CheckResult("ffmpeg", True, "6.0")
            mock_nodejs.return_value = CheckResult("nodejs", True, "v20.10.0")

            result = await validator.validate_all()

            assert result.success is False
            assert result.degraded_mode is False
            assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_degraded_mode_still_fails_on_critical(self, tmp_path: Path) -> None:
        """Test degraded mode still fails on truly critical failures (yt-dlp)."""
        config = Config(
            security=SecurityConfig(api_keys=["test"], allow_degraded_start=True),
            storage=StorageConfig(output_dir=str(tmp_path)),
            providers=ProvidersConfig(youtube=YouTubeProviderConfig(enabled=False)),
        )

        validator = StartupValidator(config)

        # Mock yt-dlp check to fail (critical)
        with (
            patch("app.core.startup.check_ytdlp") as mock_ytdlp,
            patch("app.core.startup.check_ffmpeg") as mock_ffmpeg,
            patch("app.core.startup.check_nodejs") as mock_nodejs,
        ):
            mock_ytdlp.return_value = CheckResult("ytdlp", False, error="yt-dlp not found")
            mock_ffmpeg.return_value = CheckResult("ffmpeg", True, "6.0")
            mock_nodejs.return_value = CheckResult("nodejs", True, "v20.10.0")

            result = await validator.validate_all()

            assert result.success is False
            assert "ytdlp" in str(result.errors).lower()


# =============================================================================
# Tests for full startup validation
# =============================================================================


class TestFullStartupValidation:
    """Integration tests for full startup validation."""

    @pytest.mark.asyncio
    async def test_validate_all_success(
        self, validator: StartupValidator, tmp_output_dir: Path
    ) -> None:
        """Test successful startup with all checks passing."""
        with (
            patch("app.core.startup.check_ytdlp") as mock_ytdlp,
            patch("app.core.startup.check_ffmpeg") as mock_ffmpeg,
            patch("app.core.startup.check_nodejs") as mock_nodejs,
            patch.object(validator, "configure_ytdlp_runtime"),
        ):
            mock_ytdlp.return_value = CheckResult("ytdlp", True, "2024.01.15")
            mock_ffmpeg.return_value = CheckResult("ffmpeg", True, "6.0")
            mock_nodejs.return_value = CheckResult("nodejs", True, "v20.10.0")

            result = await validator.validate_all()

            assert result.success is True
            assert result.degraded_mode is False
            assert len(result.errors) == 0
            assert len(result.checks) == 5  # ytdlp, ffmpeg, nodejs, storage, cookies

    @pytest.mark.asyncio
    async def test_validate_all_critical_failure(self, validator: StartupValidator) -> None:
        """Test startup failure on critical check failure."""
        with (
            patch("app.core.startup.check_ytdlp") as mock_ytdlp,
            patch("app.core.startup.check_ffmpeg") as mock_ffmpeg,
            patch("app.core.startup.check_nodejs") as mock_nodejs,
        ):
            mock_ytdlp.return_value = CheckResult("ytdlp", False, error="yt-dlp not found")
            mock_ffmpeg.return_value = CheckResult("ffmpeg", True, "6.0")
            mock_nodejs.return_value = CheckResult("nodejs", True, "v20.10.0")

            result = await validator.validate_all()

            assert result.success is False
            assert len(result.errors) > 0


# =============================================================================
# Tests for yt-dlp config management
# =============================================================================


class TestYtdlpConfigManagement:
    """Tests for yt-dlp config file creation."""

    def test_creates_config_file_with_node_runtime(
        self, validator: StartupValidator, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test config file is created with --js-runtimes node."""
        config_dir = tmp_path / ".config" / "yt-dlp"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))

        validator.configure_ytdlp_runtime()

        config_file = config_dir / "config"
        assert config_file.exists()
        content = config_file.read_text()
        assert "--js-runtimes node" in content

    def test_preserves_existing_config_entries(
        self, validator: StartupValidator, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test existing config entries are preserved."""
        config_dir = tmp_path / ".config" / "yt-dlp"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config"
        config_file.write_text("--no-mtime\n--embed-thumbnail\n")

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))

        validator.configure_ytdlp_runtime()

        content = config_file.read_text()
        assert "--no-mtime" in content
        assert "--embed-thumbnail" in content
        assert "--js-runtimes node" in content

    def test_does_not_duplicate_js_runtimes(
        self, validator: StartupValidator, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test --js-runtimes is not added if already present."""
        config_dir = tmp_path / ".config" / "yt-dlp"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config"
        config_file.write_text("--js-runtimes node\n")

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))

        validator.configure_ytdlp_runtime()

        content = config_file.read_text()
        assert content.count("--js-runtimes") == 1

    def test_uses_home_directory_if_no_xdg(
        self, validator: StartupValidator, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test uses ~/.config if XDG_CONFIG_HOME not set."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        validator.configure_ytdlp_runtime()

        config_file = tmp_path / ".config" / "yt-dlp" / "config"
        assert config_file.exists()
        content = config_file.read_text()
        assert "--js-runtimes node" in content


# =============================================================================
# Tests for dataclasses
# =============================================================================


class TestDataclasses:
    """Tests for ComponentCheckResult and StartupResult dataclasses."""

    def test_component_check_result_defaults(self) -> None:
        """Test ComponentCheckResult default values."""
        result = ComponentCheckResult(name="test", passed=True, critical=False)

        assert result.name == "test"
        assert result.passed is True
        assert result.critical is False
        assert result.version is None
        assert result.message is None
        assert result.details == {}

    def test_component_check_result_with_values(self) -> None:
        """Test ComponentCheckResult with all values."""
        result = ComponentCheckResult(
            name="ytdlp",
            passed=True,
            critical=True,
            version="2024.01.15",
            message="yt-dlp is available",
            details={"path": "/usr/bin/yt-dlp"},
        )

        assert result.version == "2024.01.15"
        assert result.message == "yt-dlp is available"
        assert result.details == {"path": "/usr/bin/yt-dlp"}

    def test_startup_result_defaults(self) -> None:
        """Test StartupResult default values."""
        result = StartupResult(success=True, degraded_mode=False)

        assert result.success is True
        assert result.degraded_mode is False
        assert result.checks == []
        assert result.disabled_providers == []
        assert result.errors == []
        assert result.warnings == []

    def test_startup_result_with_values(self) -> None:
        """Test StartupResult with all values."""
        check = ComponentCheckResult(name="test", passed=True, critical=False)
        result = StartupResult(
            success=True,
            degraded_mode=True,
            checks=[check],
            disabled_providers=["youtube"],
            errors=[],
            warnings=["Cookie file missing"],
        )

        assert len(result.checks) == 1
        assert result.disabled_providers == ["youtube"]
        assert result.warnings == ["Cookie file missing"]
