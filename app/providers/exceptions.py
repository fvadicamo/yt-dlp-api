"""Provider-specific exceptions."""


class ProviderError(Exception):
    """Base exception for provider errors."""

    pass


class InvalidURLError(ProviderError):
    """Raised when URL is invalid or unsupported."""

    pass


class VideoUnavailableError(ProviderError):
    """Raised when video is not accessible."""

    pass


class FormatNotFoundError(ProviderError):
    """Raised when requested format is not available."""

    pass


class DownloadError(ProviderError):
    """Raised when download operation fails."""

    pass


class AuthenticationError(ProviderError):
    """Raised when authentication fails."""

    pass


class CookieError(ProviderError):
    """Raised when cookie is invalid or expired."""

    pass


class TranscodingError(ProviderError):
    """Raised when audio/video transcoding fails."""

    pass
