"""Tests for cookie service."""

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.providers.exceptions import CookieError
from app.services.cookie_service import CookieService


@pytest.fixture
def temp_cookie_dir(tmp_path):
    """Create temporary cookie directory."""
    cookie_dir = tmp_path / "cookies"
    cookie_dir.mkdir()
    return cookie_dir


@pytest.fixture
def valid_netscape_cookie(temp_cookie_dir):
    """Create a valid Netscape format cookie file."""
    cookie_file = temp_cookie_dir / "youtube.txt"
    content = """# Netscape HTTP Cookie File
# This is a generated file! Do not edit.

.youtube.com	TRUE	/	TRUE	1735689600	CONSENT	YES+cb
.youtube.com	TRUE	/	FALSE	1735689600	VISITOR_INFO1_LIVE	abcdef123456
"""
    cookie_file.write_text(content)
    return cookie_file


@pytest.fixture
def invalid_cookie(temp_cookie_dir):
    """Create an invalid cookie file."""
    cookie_file = temp_cookie_dir / "invalid.txt"
    content = "This is not a valid cookie file"
    cookie_file.write_text(content)
    return cookie_file


@pytest.fixture
def empty_cookie(temp_cookie_dir):
    """Create an empty cookie file."""
    cookie_file = temp_cookie_dir / "empty.txt"
    cookie_file.write_text("")
    return cookie_file


@pytest.fixture
def cookie_service_config(valid_netscape_cookie):
    """Create cookie service configuration."""
    return {
        "providers": {
            "youtube": {
                "enabled": True,
                "cookie_path": str(valid_netscape_cookie),
            }
        }
    }


@pytest.fixture
def cookie_service(cookie_service_config):
    """Create cookie service instance."""
    return CookieService(cookie_service_config)


class TestCookieServiceInitialization:
    """Test cookie service initialization."""

    def test_init_loads_provider_cookies(self, cookie_service, valid_netscape_cookie):
        """Test that initialization loads provider cookies."""
        assert "youtube" in cookie_service.provider_cookies
        assert cookie_service.provider_cookies["youtube"] == str(valid_netscape_cookie)

    def test_init_skips_disabled_providers(self):
        """Test that disabled providers are skipped."""
        config = {
            "providers": {"youtube": {"enabled": False, "cookie_path": "/path/to/cookie.txt"}}
        }
        service = CookieService(config)
        assert "youtube" not in service.provider_cookies

    def test_init_creates_caches(self, cookie_service):
        """Test that caches are initialized."""
        assert cookie_service.validation_cache is not None
        assert cookie_service.file_mtimes == {}
        assert cookie_service.last_file_check == {}


class TestCookieFileLoading:
    """Test cookie file loading."""

    def test_load_cookie_file_success(self, cookie_service):
        """Test successful cookie file loading."""
        content = cookie_service.load_cookie_file("youtube")
        assert "# Netscape HTTP Cookie File" in content
        assert ".youtube.com" in content

    def test_load_cookie_file_missing_provider(self, cookie_service):
        """Test loading cookie for non-existent provider."""
        with pytest.raises(CookieError, match="No cookie path configured"):
            cookie_service.load_cookie_file("nonexistent")

    def test_load_cookie_file_not_found(self, cookie_service_config):
        """Test loading non-existent cookie file."""
        cookie_service_config["providers"]["youtube"]["cookie_path"] = "/nonexistent/cookie.txt"
        service = CookieService(cookie_service_config)

        with pytest.raises(CookieError, match="Cookie file not found"):
            service.load_cookie_file("youtube")


class TestNetscapeFormatValidation:
    """Test Netscape format validation."""

    def test_validate_netscape_format_valid(self, cookie_service):
        """Test validation of valid Netscape format."""
        content = cookie_service.load_cookie_file("youtube")
        assert cookie_service.validate_netscape_format(content, "youtube") is True

    def test_validate_netscape_format_empty(self, cookie_service):
        """Test validation of empty cookie file."""
        with pytest.raises(CookieError, match="empty"):
            cookie_service.validate_netscape_format("", "youtube")

    def test_validate_netscape_format_invalid_entries(self, cookie_service):
        """Test validation of invalid cookie entries."""
        invalid_content = """# Netscape HTTP Cookie File
.youtube.com	TRUE	/	TRUE	1735689600
"""
        with pytest.raises(CookieError, match="Invalid cookie entry"):
            cookie_service.validate_netscape_format(invalid_content, "youtube")

    def test_validate_netscape_format_no_entries(self, cookie_service):
        """Test validation with only comments."""
        content = """# Netscape HTTP Cookie File
# Just comments
"""
        with pytest.raises(CookieError, match="No valid cookie entries"):
            cookie_service.validate_netscape_format(content, "youtube")

    def test_validate_netscape_format_without_header(self, cookie_service):
        """Test validation without Netscape header but valid entries."""
        content = ".youtube.com	TRUE	/	TRUE	1735689600	CONSENT	YES+cb"
        assert cookie_service.validate_netscape_format(content, "youtube") is True


class TestCookieAgeChecking:
    """Test cookie age checking."""

    def test_check_cookie_age_recent(self, cookie_service):
        """Test age check for recent cookie."""
        warning = cookie_service.check_cookie_age("youtube")
        assert warning is None

    def test_check_cookie_age_old(self, cookie_service, valid_netscape_cookie):
        """Test age check for old cookie."""
        # Set file modification time to 8 days ago
        old_time = time.time() - (8 * 24 * 3600)
        Path(valid_netscape_cookie).touch()
        import os

        os.utime(valid_netscape_cookie, (old_time, old_time))

        warning = cookie_service.check_cookie_age("youtube")
        assert warning is not None
        assert "8 days old" in warning

    def test_get_cookie_age_hours(self, cookie_service):
        """Test getting cookie age in hours."""
        age_hours = cookie_service.get_cookie_age_hours("youtube")
        assert age_hours is not None
        assert age_hours >= 0

    def test_get_cookie_age_hours_missing_provider(self, cookie_service):
        """Test getting age for missing provider."""
        age_hours = cookie_service.get_cookie_age_hours("nonexistent")
        assert age_hours is None


class TestCookieValidation:
    """Test cookie validation."""

    def test_validate_cookie_file_success(self, cookie_service):
        """Test successful cookie file validation."""
        cookie_service.validate_cookie_file("youtube")
        # Should not raise exception

    def test_validate_cookie_file_invalid(self, temp_cookie_dir):
        """Test validation of invalid cookie file."""
        config = {
            "providers": {
                "youtube": {
                    "enabled": True,
                    "cookie_path": str(temp_cookie_dir / "invalid.txt"),
                }
            }
        }
        service = CookieService(config)

        # Create invalid cookie
        (temp_cookie_dir / "invalid.txt").write_text("invalid content")

        with pytest.raises(CookieError):
            service.validate_cookie_file("youtube")


class TestCacheInvalidation:
    """Test cache invalidation."""

    def test_check_file_modification_new_file(self, cookie_service):
        """Test file modification detection for new file."""
        modified = cookie_service._check_file_modification("youtube")
        assert modified is True  # First check always returns True

    def test_check_file_modification_unchanged(self, cookie_service):
        """Test file modification detection for unchanged file."""
        # First check
        cookie_service._check_file_modification("youtube")

        # Second check without modification
        modified = cookie_service._check_file_modification("youtube")
        assert modified is False

    def test_check_file_modification_changed(self, cookie_service, valid_netscape_cookie):
        """Test file modification detection after change."""
        # First check
        cookie_service._check_file_modification("youtube")

        # Modify file
        time.sleep(0.1)  # Ensure mtime changes
        valid_netscape_cookie.touch()

        # Second check
        modified = cookie_service._check_file_modification("youtube")
        assert modified is True

    def test_should_check_file_interval(self, cookie_service):
        """Test file check interval."""
        # First check should return True
        assert cookie_service._should_check_file("youtube") is True

        # Immediate second check should return False
        assert cookie_service._should_check_file("youtube") is False

    def test_invalidate_cache(self, cookie_service):
        """Test cache invalidation."""
        # Add something to cache
        cookie_service.validation_cache["youtube"] = True

        # Invalidate
        cookie_service._invalidate_cache("youtube")

        # Should be removed
        assert "youtube" not in cookie_service.validation_cache


class TestCookieValidationWithCache:
    """Test cookie validation with caching."""

    @pytest.mark.asyncio
    async def test_validate_cookie_caches_result(self, cookie_service):
        """Test that validation result is cached."""
        with patch.object(
            cookie_service, "_test_youtube_authentication", new_callable=AsyncMock
        ) as mock_auth:
            mock_auth.return_value = True

            # First call
            result1 = await cookie_service.validate_cookie("youtube")
            assert result1 is True
            assert mock_auth.call_count == 1

            # Second call should use cache
            result2 = await cookie_service.validate_cookie("youtube")
            assert result2 is True
            assert mock_auth.call_count == 1  # Not called again

    @pytest.mark.asyncio
    async def test_validate_cookie_invalidates_on_file_change(
        self, cookie_service, valid_netscape_cookie
    ):
        """Test that cache is invalidated when file changes."""
        with patch.object(
            cookie_service, "_test_youtube_authentication", new_callable=AsyncMock
        ) as mock_auth:
            mock_auth.return_value = True

            # First validation
            await cookie_service.validate_cookie("youtube")
            assert mock_auth.call_count == 1

            # Modify file
            time.sleep(0.1)
            valid_netscape_cookie.touch()

            # Force file check
            cookie_service.last_file_check["youtube"] = 0

            # Second validation should detect change and revalidate
            await cookie_service.validate_cookie("youtube")
            assert mock_auth.call_count == 2

    @pytest.mark.asyncio
    async def test_validate_cookie_does_not_cache_failure(self, cookie_service):
        """Test that validation failures are NOT cached.

        This ensures consistent behavior: validate_cookie() always raises
        CookieError on failure, never returns False from cache.
        """
        with patch.object(
            cookie_service, "_test_youtube_authentication", new_callable=AsyncMock
        ) as mock_auth:
            mock_auth.side_effect = CookieError("Auth failed")

            # First call should fail and raise
            with pytest.raises(CookieError):
                await cookie_service.validate_cookie("youtube")

            # Result should NOT be cached
            assert "youtube" not in cookie_service.validation_cache

            # Second call should also raise (not return False from cache)
            with pytest.raises(CookieError):
                await cookie_service.validate_cookie("youtube")

            # Both calls should have attempted validation
            assert mock_auth.call_count == 2


class TestYouTubeAuthentication:
    """Test YouTube authentication."""

    @pytest.mark.asyncio
    async def test_youtube_authentication_success(self, cookie_service):
        """Test successful YouTube authentication."""
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            # Mock successful yt-dlp execution
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"", b""))
            mock_subprocess.return_value = mock_process

            result = await cookie_service._test_youtube_authentication()
            assert result is True

    @pytest.mark.asyncio
    async def test_youtube_authentication_failure(self, cookie_service):
        """Test failed YouTube authentication."""
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            # Mock failed yt-dlp execution
            mock_process = AsyncMock()
            mock_process.returncode = 1
            mock_process.communicate = AsyncMock(
                return_value=(b"", b"ERROR: Unable to extract video data")
            )
            mock_subprocess.return_value = mock_process

            with pytest.raises(CookieError, match="authentication failed"):
                await cookie_service._test_youtube_authentication()

    @pytest.mark.asyncio
    async def test_youtube_authentication_timeout(self, cookie_service):
        """Test YouTube authentication timeout."""
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            # Mock timeout
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
            mock_subprocess.return_value = mock_process

            with pytest.raises(CookieError, match="timed out"):
                await cookie_service._test_youtube_authentication()

    @pytest.mark.asyncio
    async def test_youtube_authentication_ytdlp_not_found(self, cookie_service):
        """Test YouTube authentication when yt-dlp is not installed."""
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_subprocess.side_effect = FileNotFoundError()

            with pytest.raises(CookieError, match="yt-dlp is not installed"):
                await cookie_service._test_youtube_authentication()


class TestCookieReload:
    """Test cookie reload functionality."""

    @pytest.mark.asyncio
    async def test_reload_cookie_success(self, cookie_service):
        """Test successful cookie reload."""
        with patch.object(
            cookie_service, "validate_cookie", new_callable=AsyncMock
        ) as mock_validate:
            mock_validate.return_value = True

            result = await cookie_service.reload_cookie("youtube")

            assert result["success"] is True
            assert result["provider"] == "youtube"
            assert "reloaded and validated successfully" in result["message"]

    @pytest.mark.asyncio
    async def test_reload_cookie_validation_failure(self, cookie_service):
        """Test cookie reload with validation failure."""
        # Set initial valid state
        cookie_service.validation_cache["youtube"] = True

        with patch.object(
            cookie_service, "validate_cookie", new_callable=AsyncMock
        ) as mock_validate:
            mock_validate.return_value = False

            with pytest.raises(CookieError, match="failed validation"):
                await cookie_service.reload_cookie("youtube")

            # Should rollback to previous state
            assert cookie_service.validation_cache.get("youtube") is True

    @pytest.mark.asyncio
    async def test_reload_cookie_invalid_provider(self, cookie_service):
        """Test reload for non-existent provider."""
        with pytest.raises(CookieError, match="not configured"):
            await cookie_service.reload_cookie("nonexistent")

    @pytest.mark.asyncio
    async def test_reload_cookie_rollback_on_error(self, cookie_service):
        """Test rollback on reload error."""
        # Set initial state
        cookie_service.validation_cache["youtube"] = True

        with patch.object(
            cookie_service, "validate_cookie", new_callable=AsyncMock
        ) as mock_validate:
            mock_validate.side_effect = Exception("Unexpected error")

            with pytest.raises(CookieError, match="Failed to reload"):
                await cookie_service.reload_cookie("youtube")

            # Should preserve previous state
            assert cookie_service.validation_cache.get("youtube") is True


class TestCookieServiceUtilities:
    """Test utility methods."""

    def test_list_providers_with_cookies(self, cookie_service):
        """Test listing providers with cookie status."""
        providers = cookie_service.list_providers_with_cookies()

        assert "youtube" in providers
        assert providers["youtube"]["exists"] is True
        assert providers["youtube"]["age_hours"] is not None

    def test_get_validation_cache_status(self, cookie_service):
        """Test getting validation cache status."""
        # Add something to cache
        cookie_service.validation_cache["youtube"] = True

        status = cookie_service.get_validation_cache_status()

        assert "youtube" in status
        assert status["youtube"]["cached"] is True
        assert status["youtube"]["is_valid"] is True
