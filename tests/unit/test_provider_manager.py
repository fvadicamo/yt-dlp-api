"""Tests for the provider manager (registration, selection, error isolation).

Covers requirement 34 (Provider Abstraction), historical task 2.4.
"""

from typing import Dict, List, Optional

import pytest

from app.models.video import DownloadResult, VideoFormat
from app.providers.base import VideoProvider
from app.providers.exceptions import InvalidURLError, ProviderError
from app.providers.manager import ProviderManager


class FakeProvider(VideoProvider):
    """Minimal in-memory provider for manager tests."""

    def __init__(self, accepts: str = "", raise_on_validate: bool = False):
        """Initialize with a URL substring to accept.

        Args:
            accepts: Substring that makes validate_url return True.
            raise_on_validate: If True, validate_url raises RuntimeError.
        """
        self.accepts = accepts
        self.raise_on_validate = raise_on_validate

    def validate_url(self, url: str) -> bool:
        """Accept URLs containing the configured substring."""
        if self.raise_on_validate:
            raise RuntimeError("validator exploded")
        return bool(self.accepts) and self.accepts in url

    async def get_info(
        self, url: str, include_formats: bool = False, include_subtitles: bool = False
    ) -> Dict:
        """Return a static info payload."""
        return {"url": url}

    async def list_formats(self, url: str) -> List[VideoFormat]:
        """Return no formats."""
        return []

    async def download(
        self,
        url: str,
        format_id: Optional[str] = None,
        output_template: Optional[str] = None,
        extract_audio: bool = False,
        audio_format: Optional[str] = None,
        include_subtitles: bool = False,
        subtitle_lang: Optional[str] = None,
    ) -> DownloadResult:
        """Not used by manager tests."""
        raise NotImplementedError

    def get_cookie_path(self) -> Optional[str]:
        """No cookies needed."""
        return None


@pytest.fixture
def manager() -> ProviderManager:
    """Fresh provider manager."""
    return ProviderManager()


class TestRegistrationAndStatus:
    """Provider registration, enable/disable, listing."""

    def test_register_enabled_by_default(self, manager):
        """Registered providers are enabled unless stated otherwise."""
        manager.register_provider("youtube", FakeProvider("youtube.com"))

        assert manager.is_provider_enabled("youtube") is True
        assert manager.list_providers() == {"youtube": True}

    def test_register_disabled(self, manager):
        """Providers can be registered in disabled state."""
        manager.register_provider("vimeo", FakeProvider("vimeo.com"), enabled=False)

        assert manager.is_provider_enabled("vimeo") is False
        assert manager.list_providers() == {"vimeo": False}

    def test_enable_and_disable(self, manager):
        """Enable/disable toggle the provider state."""
        manager.register_provider("youtube", FakeProvider("youtube.com"), enabled=False)

        manager.enable_provider("youtube")
        assert manager.is_provider_enabled("youtube") is True

        manager.disable_provider("youtube")
        assert manager.is_provider_enabled("youtube") is False

    def test_enable_unregistered_raises(self, manager):
        """Enabling an unknown provider raises ValueError."""
        with pytest.raises(ValueError, match="not registered"):
            manager.enable_provider("missing")

    def test_disable_unregistered_raises(self, manager):
        """Disabling an unknown provider raises ValueError."""
        with pytest.raises(ValueError, match="not registered"):
            manager.disable_provider("missing")

    def test_is_enabled_unknown_provider(self, manager):
        """Unknown providers report as disabled."""
        assert manager.is_provider_enabled("missing") is False

    def test_get_provider_by_name(self, manager):
        """Lookup by name returns the instance or None."""
        provider = FakeProvider("youtube.com")
        manager.register_provider("youtube", provider)

        assert manager.get_provider_by_name("youtube") is provider
        assert manager.get_provider_by_name("missing") is None


class TestUrlSelection:
    """URL-based provider selection with error isolation."""

    def test_selects_matching_provider(self, manager):
        """The first enabled provider validating the URL wins."""
        youtube = FakeProvider("youtube.com")
        manager.register_provider("youtube", youtube)

        selected = manager.get_provider_for_url("https://youtube.com/watch?v=x")

        assert selected is youtube

    def test_skips_disabled_provider(self, manager):
        """Disabled providers are never selected."""
        manager.register_provider("youtube", FakeProvider("youtube.com"), enabled=False)

        with pytest.raises(InvalidURLError, match="No provider available"):
            manager.get_provider_for_url("https://youtube.com/watch?v=x")

    def test_no_match_raises_invalid_url(self, manager):
        """URL matched by no provider raises InvalidURLError."""
        manager.register_provider("youtube", FakeProvider("youtube.com"))

        with pytest.raises(InvalidURLError, match="No provider available"):
            manager.get_provider_for_url("https://example.com/video")

    def test_validation_error_is_isolated(self, manager):
        """A provider whose validate_url raises must not block the others."""
        manager.register_provider("broken", FakeProvider(raise_on_validate=True))
        good = FakeProvider("youtube.com")
        manager.register_provider("youtube", good)

        selected = manager.get_provider_for_url("https://youtube.com/watch?v=x")

        assert selected is good

    def test_all_validators_failing_raises_invalid_url(self, manager):
        """If every provider errors out, selection fails cleanly."""
        manager.register_provider("broken", FakeProvider(raise_on_validate=True))

        with pytest.raises(InvalidURLError, match="No provider available"):
            manager.get_provider_for_url("https://youtube.com/watch?v=x")


class TestErrorIsolation:
    """Wrapping semantics of execute_with_error_isolation."""

    @pytest.mark.asyncio
    async def test_success_returns_result(self, manager):
        """Successful operations pass their result through."""

        async def operation(value):
            return value * 2

        result = await manager.execute_with_error_isolation("youtube", operation, 21)

        assert result == 42

    @pytest.mark.asyncio
    async def test_provider_error_reraised(self, manager):
        """Provider errors propagate unchanged."""

        async def operation():
            raise InvalidURLError("bad url")

        with pytest.raises(InvalidURLError, match="bad url"):
            await manager.execute_with_error_isolation("youtube", operation)

    @pytest.mark.asyncio
    async def test_unexpected_error_wrapped(self, manager):
        """Unexpected exceptions are wrapped in ProviderError with context."""

        async def operation():
            raise RuntimeError("boom")

        with pytest.raises(ProviderError, match="unexpected error: boom") as exc_info:
            await manager.execute_with_error_isolation("youtube", operation)

        assert isinstance(exc_info.value.__cause__, RuntimeError)
