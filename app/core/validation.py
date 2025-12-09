"""Input validation utilities for the API layer.

This module provides validation functions for URLs, format IDs, and other
parameters that are used across API endpoints.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Optional, Set
from urllib.parse import urlparse

import structlog

logger = structlog.get_logger(__name__)


class AudioFormat(str, Enum):
    """Supported audio output formats."""

    MP3 = "mp3"
    M4A = "m4a"
    WAV = "wav"
    OPUS = "opus"


class AudioQuality(str, Enum):
    """Supported audio quality levels."""

    LOW = "128"
    MEDIUM = "192"
    HIGH = "320"


@dataclass(frozen=True)
class ValidationResult:
    """Result of a validation operation."""

    is_valid: bool
    error_message: Optional[str] = None
    sanitized_value: Optional[str] = None


class URLValidator:
    """Validates URLs against an allowed domain whitelist."""

    # Default allowed domains for video providers
    DEFAULT_ALLOWED_DOMAINS: FrozenSet[str] = frozenset(
        {
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "youtu.be",
        }
    )

    # Dangerous URL schemes that should always be rejected
    DANGEROUS_SCHEMES: FrozenSet[str] = frozenset(
        {
            "javascript",
            "data",
            "file",
            "vbscript",
            "about",
        }
    )

    def __init__(self, allowed_domains: Optional[Set[str]] = None):
        """
        Initialize URL validator.

        Args:
            allowed_domains: Set of allowed domain names. Uses default if not provided.
        """
        self.allowed_domains = allowed_domains or self.DEFAULT_ALLOWED_DOMAINS

    def validate(self, url: str) -> ValidationResult:  # noqa: C901
        """Validate a URL against the whitelist.

        Args:
            url: URL to validate

        Returns:
            ValidationResult with validation status and any error message
        """
        if not url or not isinstance(url, str):
            return ValidationResult(
                is_valid=False, error_message="URL is required and must be a string"
            )

        url = url.strip()
        if not url:
            return ValidationResult(is_valid=False, error_message="URL cannot be empty")

        try:
            parsed = urlparse(url)
        except Exception as e:
            logger.warning("URL parsing failed", url=url, error=str(e))
            return ValidationResult(is_valid=False, error_message="Invalid URL format")

        # Check for dangerous schemes
        scheme = parsed.scheme.lower() if parsed.scheme else ""
        if scheme in self.DANGEROUS_SCHEMES:
            logger.warning("Dangerous URL scheme detected", url=url, scheme=scheme)
            return ValidationResult(
                is_valid=False, error_message=f"URL scheme '{scheme}' is not allowed"
            )

        # Require http or https
        if scheme not in ("http", "https", ""):
            return ValidationResult(
                is_valid=False, error_message="URL must use http or https scheme"
            )

        # Extract and validate domain
        netloc = parsed.netloc.lower()
        if not netloc:
            # Handle URLs without scheme (e.g., "youtube.com/watch?v=xxx")
            # Try to extract domain from path
            path_parts = parsed.path.split("/")
            if path_parts:
                potential_domain = path_parts[0].lower()
                if potential_domain and "." in potential_domain:
                    netloc = potential_domain

        if not netloc:
            return ValidationResult(is_valid=False, error_message="URL must include a valid domain")

        # Remove port number if present
        domain = netloc.split(":")[0]

        # Check if domain is in whitelist
        if domain not in self.allowed_domains:
            logger.debug("Domain not in whitelist", url=url, domain=domain)
            return ValidationResult(
                is_valid=False,
                error_message=f"Domain '{domain}' is not in the allowed list",
            )

        logger.debug("URL validated successfully", url=url, domain=domain)
        return ValidationResult(is_valid=True, sanitized_value=url)

    def is_valid(self, url: str) -> bool:
        """
        Quick check if URL is valid.

        Args:
            url: URL to validate

        Returns:
            True if URL is valid, False otherwise
        """
        return self.validate(url).is_valid


class FormatValidator:
    """Validates yt-dlp format IDs and specifications."""

    # Valid format ID pattern: alphanumeric, underscore, hyphen, plus (for merged formats)
    FORMAT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_+-]+$")

    # Maximum length for format ID
    MAX_FORMAT_ID_LENGTH = 50

    # Common special format selectors
    SPECIAL_SELECTORS: FrozenSet[str] = frozenset(
        {
            "best",
            "worst",
            "bestvideo",
            "worstvideo",
            "bestaudio",
            "worstaudio",
            "bestvideo+bestaudio",
            "best[height<=720]",
            "best[height<=1080]",
        }
    )

    def validate_format_id(self, format_id: str) -> ValidationResult:
        """
        Validate a format ID.

        Args:
            format_id: Format ID to validate

        Returns:
            ValidationResult with validation status
        """
        if not format_id or not isinstance(format_id, str):
            return ValidationResult(is_valid=False, error_message="Format ID is required")

        format_id = format_id.strip()

        if len(format_id) > self.MAX_FORMAT_ID_LENGTH:
            return ValidationResult(
                is_valid=False,
                error_message=f"Format ID exceeds maximum length of {self.MAX_FORMAT_ID_LENGTH}",
            )

        # Allow special selectors
        if format_id.lower() in self.SPECIAL_SELECTORS:
            return ValidationResult(is_valid=True, sanitized_value=format_id)

        # Check pattern for standard format IDs
        if not self.FORMAT_ID_PATTERN.match(format_id):
            return ValidationResult(
                is_valid=False,
                error_message="Format ID contains invalid characters",
            )

        return ValidationResult(is_valid=True, sanitized_value=format_id)

    def is_valid_format_id(self, format_id: str) -> bool:
        """Quick check if format ID is valid."""
        return self.validate_format_id(format_id).is_valid


class ParameterValidator:
    """Validates API request parameters."""

    def validate_audio_format(self, audio_format: str) -> ValidationResult:
        """
        Validate audio format parameter.

        Args:
            audio_format: Audio format string

        Returns:
            ValidationResult with validation status
        """
        if not audio_format:
            return ValidationResult(is_valid=False, error_message="Audio format is required")

        try:
            AudioFormat(audio_format.lower())
            return ValidationResult(is_valid=True, sanitized_value=audio_format.lower())
        except ValueError:
            valid_formats = [f.value for f in AudioFormat]
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid audio format. Valid options: {', '.join(valid_formats)}",
            )

    def validate_audio_quality(self, quality: str) -> ValidationResult:
        """
        Validate audio quality parameter.

        Args:
            quality: Audio quality string (bitrate)

        Returns:
            ValidationResult with validation status
        """
        if not quality:
            return ValidationResult(is_valid=False, error_message="Audio quality is required")

        try:
            AudioQuality(quality)
            return ValidationResult(is_valid=True, sanitized_value=quality)
        except ValueError:
            valid_qualities = [f.value for f in AudioQuality]
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid audio quality. Valid options: {', '.join(valid_qualities)}kbps",
            )

    def validate_language_code(self, lang_code: str) -> ValidationResult:
        """
        Validate language code for subtitles.

        Args:
            lang_code: ISO 639-1 or 639-2 language code

        Returns:
            ValidationResult with validation status
        """
        if not lang_code or not isinstance(lang_code, str):
            return ValidationResult(is_valid=False, error_message="Language code is required")

        lang_code = lang_code.strip().lower()

        # ISO 639-1 (2 chars) or ISO 639-2 (3 chars), optionally with region (e.g., en-US)
        pattern = re.compile(r"^[a-z]{2,3}(-[a-zA-Z]{2,4})?$")

        if not pattern.match(lang_code):
            return ValidationResult(
                is_valid=False,
                error_message="Invalid language code format. Use ISO 639 format (e.g., 'en', 'en-US')",
            )

        return ValidationResult(is_valid=True, sanitized_value=lang_code)

    def validate_positive_integer(
        self, value: int, name: str, max_value: Optional[int] = None
    ) -> ValidationResult:
        """
        Validate a positive integer parameter.

        Args:
            value: Integer value to validate
            name: Parameter name for error messages
            max_value: Optional maximum allowed value

        Returns:
            ValidationResult with validation status
        """
        if not isinstance(value, int) or isinstance(value, bool):
            return ValidationResult(is_valid=False, error_message=f"{name} must be an integer")

        if value <= 0:
            return ValidationResult(
                is_valid=False, error_message=f"{name} must be a positive integer"
            )

        if max_value is not None and value > max_value:
            return ValidationResult(
                is_valid=False,
                error_message=f"{name} exceeds maximum allowed value of {max_value}",
            )

        return ValidationResult(is_valid=True, sanitized_value=str(value))


# Singleton instances for convenience
url_validator = URLValidator()
format_validator = FormatValidator()
parameter_validator = ParameterValidator()


def validate_youtube_url(url: str) -> bool:
    """
    Convenience function to validate YouTube URLs.

    Args:
        url: URL to validate

    Returns:
        True if URL is a valid YouTube URL
    """
    return url_validator.is_valid(url)


def validate_format_id(format_id: str) -> bool:
    """
    Convenience function to validate format IDs.

    Args:
        format_id: Format ID to validate

    Returns:
        True if format ID is valid
    """
    return format_validator.is_valid_format_id(format_id)
