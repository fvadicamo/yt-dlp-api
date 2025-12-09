"""Tests for input validation utilities."""

import pytest

from app.core.validation import (
    AudioFormat,
    AudioQuality,
    FormatValidator,
    ParameterValidator,
    URLValidator,
    ValidationResult,
    format_validator,
    parameter_validator,
    url_validator,
    validate_format_id,
    validate_youtube_url,
)


class TestURLValidator:
    """Tests for URLValidator class."""

    @pytest.fixture
    def validator(self) -> URLValidator:
        """Create a URL validator instance."""
        return URLValidator()

    # Valid YouTube URLs
    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            "http://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=abc123-_XYZ",
            "https://youtube.com/shorts/dQw4w9WgXcQ",
        ],
    )
    def test_valid_youtube_urls(self, validator: URLValidator, url: str):
        """Test that valid YouTube URLs are accepted."""
        result = validator.validate(url)
        assert result.is_valid is True
        assert result.error_message is None

    # Invalid domains
    @pytest.mark.parametrize(
        "url,expected_domain",
        [
            ("https://vimeo.com/123456", "vimeo.com"),
            ("https://dailymotion.com/video/abc", "dailymotion.com"),
            ("https://facebook.com/video/123", "facebook.com"),
            ("https://evil-youtube.com/watch?v=abc", "evil-youtube.com"),
            ("https://youtube.com.evil.com/watch?v=abc", "youtube.com.evil.com"),
        ],
    )
    def test_invalid_domains_rejected(
        self, validator: URLValidator, url: str, expected_domain: str
    ):
        """Test that non-whitelisted domains are rejected."""
        result = validator.validate(url)
        assert result.is_valid is False
        assert expected_domain in result.error_message

    # Dangerous URL schemes
    @pytest.mark.parametrize(
        "url,scheme",
        [
            ("javascript:alert('xss')", "javascript"),
            ("data:text/html,<script>alert('xss')</script>", "data"),
            ("file:///etc/passwd", "file"),
            ("vbscript:msgbox('xss')", "vbscript"),
        ],
    )
    def test_dangerous_schemes_rejected(self, validator: URLValidator, url: str, scheme: str):
        """Test that dangerous URL schemes are rejected."""
        result = validator.validate(url)
        assert result.is_valid is False
        assert "not allowed" in result.error_message.lower()

    # Empty and invalid inputs
    @pytest.mark.parametrize(
        "url,expected_error",
        [
            ("", "required"),
            ("   ", "cannot be empty"),
            (None, "required"),
            (123, "must be a string"),
            ([], "must be a string"),
        ],
    )
    def test_empty_and_invalid_inputs(self, validator: URLValidator, url, expected_error: str):
        """Test that empty and invalid inputs are rejected."""
        result = validator.validate(url)
        assert result.is_valid is False
        assert expected_error in result.error_message.lower()

    def test_url_with_port_number(self, validator: URLValidator):
        """Test URL with port number is handled correctly."""
        result = validator.validate("https://youtube.com:443/watch?v=abc")
        assert result.is_valid is True

    def test_url_with_embedded_credentials_rejected(self, validator: URLValidator):
        """Test that URLs with embedded credentials are correctly rejected."""
        # Attack: URL with credentials that makes netloc look like youtube.com
        # but actually points to evil.com
        malicious_url = "https://youtube.com:x@evil.com/malicious"
        result = validator.validate(malicious_url)
        assert result.is_valid is False
        # Should reject evil.com, not accept youtube.com
        assert (
            "evil.com" in result.error_message or "not in the allowed list" in result.error_message
        )

    def test_url_with_credentials_and_port_rejected(self, validator: URLValidator):
        """Test that URLs with both credentials and port are handled correctly."""
        # Another attack vector: credentials + port
        malicious_url = "https://youtube.com:password@evil.com:443/malicious"
        result = validator.validate(malicious_url)
        assert result.is_valid is False
        assert (
            "evil.com" in result.error_message or "not in the allowed list" in result.error_message
        )

    def test_custom_allowed_domains(self):
        """Test validator with custom domain whitelist."""
        custom_validator = URLValidator(allowed_domains={"example.com", "test.org"})

        # Custom domain should be allowed
        result = custom_validator.validate("https://example.com/video")
        assert result.is_valid is True

        # YouTube should now be rejected
        result = custom_validator.validate("https://youtube.com/watch?v=abc")
        assert result.is_valid is False

    def test_is_valid_convenience_method(self, validator: URLValidator):
        """Test the is_valid convenience method."""
        assert validator.is_valid("https://youtube.com/watch?v=abc") is True
        assert validator.is_valid("https://evil.com/video") is False


class TestFormatValidator:
    """Tests for FormatValidator class."""

    @pytest.fixture
    def validator(self) -> FormatValidator:
        """Create a format validator instance."""
        return FormatValidator()

    # Valid format IDs
    @pytest.mark.parametrize(
        "format_id",
        [
            "22",
            "137",
            "bestvideo",
            "bestaudio",
            "best",
            "worst",
            "137+140",
            "bestvideo+bestaudio",
            "hls-720p",
            "dash_video_1080",
            "format_123-abc",
        ],
    )
    def test_valid_format_ids(self, validator: FormatValidator, format_id: str):
        """Test that valid format IDs are accepted."""
        result = validator.validate_format_id(format_id)
        assert result.is_valid is True
        assert result.error_message is None

    # Invalid format IDs
    @pytest.mark.parametrize(
        "format_id",
        [
            "format with spaces",
            "format;injection",
            "format'sql",
            "format<script>",
            "../../../etc/passwd",
            "format\x00null",
        ],
    )
    def test_invalid_format_ids_rejected(self, validator: FormatValidator, format_id: str):
        """Test that invalid format IDs are rejected."""
        result = validator.validate_format_id(format_id)
        assert result.is_valid is False
        assert "invalid characters" in result.error_message.lower()

    def test_format_id_max_length(self, validator: FormatValidator):
        """Test that overly long format IDs are rejected."""
        long_format_id = "a" * 100
        result = validator.validate_format_id(long_format_id)
        assert result.is_valid is False
        assert "maximum length" in result.error_message.lower()

    def test_empty_format_id_rejected(self, validator: FormatValidator):
        """Test that empty format IDs are rejected."""
        result = validator.validate_format_id("")
        assert result.is_valid is False
        assert "required" in result.error_message.lower()

    def test_whitespace_only_format_id_rejected(self, validator: FormatValidator):
        """Test that format IDs containing only whitespace are rejected."""
        result = validator.validate_format_id("   ")
        assert result.is_valid is False
        assert "cannot be empty" in result.error_message.lower()

        result = validator.validate_format_id("\t\t")
        assert result.is_valid is False
        assert "cannot be empty" in result.error_message.lower()

        result = validator.validate_format_id("\n\n")
        assert result.is_valid is False
        assert "cannot be empty" in result.error_message.lower()

    def test_none_format_id_rejected(self, validator: FormatValidator):
        """Test that None format ID is rejected."""
        result = validator.validate_format_id(None)
        assert result.is_valid is False

    def test_is_valid_format_id_convenience(self, validator: FormatValidator):
        """Test the is_valid_format_id convenience method."""
        assert validator.is_valid_format_id("22") is True
        assert validator.is_valid_format_id("invalid;format") is False

    def test_special_selectors_with_brackets(self, validator: FormatValidator):
        """Test that special selectors with brackets are accepted (case-insensitive)."""
        # Test lowercase
        result = validator.validate_format_id("best[height<=720]")
        assert result.is_valid is True
        assert result.error_message is None

        result = validator.validate_format_id("best[height<=1080]")
        assert result.is_valid is True
        assert result.error_message is None

        # Test uppercase (should also work due to case-insensitive comparison)
        result = validator.validate_format_id("BEST[HEIGHT<=720]")
        assert result.is_valid is True
        assert result.error_message is None

        result = validator.validate_format_id("BEST[HEIGHT<=1080]")
        assert result.is_valid is True
        assert result.error_message is None

        # Test mixed case
        result = validator.validate_format_id("Best[Height<=720]")
        assert result.is_valid is True
        assert result.error_message is None


class TestParameterValidator:
    """Tests for ParameterValidator class."""

    @pytest.fixture
    def validator(self) -> ParameterValidator:
        """Create a parameter validator instance."""
        return ParameterValidator()

    # Audio format validation
    @pytest.mark.parametrize(
        "audio_format",
        ["mp3", "MP3", "m4a", "M4A", "wav", "WAV", "opus", "OPUS"],
    )
    def test_valid_audio_formats(self, validator: ParameterValidator, audio_format: str):
        """Test that valid audio formats are accepted."""
        result = validator.validate_audio_format(audio_format)
        assert result.is_valid is True
        assert result.sanitized_value == audio_format.lower()

    @pytest.mark.parametrize(
        "audio_format",
        ["mp4", "flac", "aac", "wma", "invalid"],
    )
    def test_invalid_audio_formats(self, validator: ParameterValidator, audio_format: str):
        """Test that invalid audio formats are rejected."""
        result = validator.validate_audio_format(audio_format)
        assert result.is_valid is False
        assert "invalid audio format" in result.error_message.lower()

    def test_empty_audio_format_rejected(self, validator: ParameterValidator):
        """Test that empty audio format is rejected."""
        result = validator.validate_audio_format("")
        assert result.is_valid is False
        assert "required" in result.error_message.lower()

    # Audio quality validation
    @pytest.mark.parametrize("quality", ["128", "192", "320"])
    def test_valid_audio_qualities(self, validator: ParameterValidator, quality: str):
        """Test that valid audio qualities are accepted."""
        result = validator.validate_audio_quality(quality)
        assert result.is_valid is True

    @pytest.mark.parametrize("quality", ["64", "256", "512", "invalid", ""])
    def test_invalid_audio_qualities(self, validator: ParameterValidator, quality: str):
        """Test that invalid audio qualities are rejected."""
        result = validator.validate_audio_quality(quality)
        assert result.is_valid is False

    # Language code validation
    @pytest.mark.parametrize(
        "lang_code",
        ["en", "EN", "en-US", "en-us", "pt-BR", "zh-Hans", "spa", "deu"],
    )
    def test_valid_language_codes(self, validator: ParameterValidator, lang_code: str):
        """Test that valid language codes are accepted."""
        result = validator.validate_language_code(lang_code)
        assert result.is_valid is True
        assert result.sanitized_value == lang_code.strip().lower()

    @pytest.mark.parametrize(
        "lang_code",
        ["e", "english", "en_US", "12", "en-USA-extra", "", None],
    )
    def test_invalid_language_codes(self, validator: ParameterValidator, lang_code):
        """Test that invalid language codes are rejected."""
        result = validator.validate_language_code(lang_code)
        assert result.is_valid is False

    # Positive integer validation
    def test_valid_positive_integers(self, validator: ParameterValidator):
        """Test that valid positive integers are accepted."""
        result = validator.validate_positive_integer(10, "count")
        assert result.is_valid is True

        result = validator.validate_positive_integer(100, "count", max_value=200)
        assert result.is_valid is True

    def test_invalid_positive_integers(self, validator: ParameterValidator):
        """Test that invalid positive integers are rejected."""
        # Zero
        result = validator.validate_positive_integer(0, "count")
        assert result.is_valid is False
        assert "positive" in result.error_message.lower()

        # Negative
        result = validator.validate_positive_integer(-5, "count")
        assert result.is_valid is False

        # Exceeds max
        result = validator.validate_positive_integer(500, "count", max_value=100)
        assert result.is_valid is False
        assert "maximum" in result.error_message.lower()

    def test_non_integer_rejected(self, validator: ParameterValidator):
        """Test that non-integers are rejected."""
        result = validator.validate_positive_integer("10", "count")
        assert result.is_valid is False
        assert "integer" in result.error_message.lower()

        # Boolean is not accepted even though bool is subclass of int
        result = validator.validate_positive_integer(True, "count")
        assert result.is_valid is False


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_valid_result(self):
        """Test creating a valid result."""
        result = ValidationResult(is_valid=True, sanitized_value="test")
        assert result.is_valid is True
        assert result.error_message is None
        assert result.sanitized_value == "test"

    def test_invalid_result(self):
        """Test creating an invalid result."""
        result = ValidationResult(is_valid=False, error_message="Error occurred")
        assert result.is_valid is False
        assert result.error_message == "Error occurred"
        assert result.sanitized_value is None

    def test_result_is_immutable(self):
        """Test that ValidationResult is immutable (frozen dataclass)."""
        result = ValidationResult(is_valid=True)
        with pytest.raises(AttributeError):
            result.is_valid = False


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_validate_youtube_url(self):
        """Test the validate_youtube_url convenience function."""
        assert validate_youtube_url("https://youtube.com/watch?v=abc") is True
        assert validate_youtube_url("https://evil.com/video") is False

    def test_validate_format_id(self):
        """Test the validate_format_id convenience function."""
        assert validate_format_id("22") is True
        assert validate_format_id("invalid;chars") is False


class TestSingletonInstances:
    """Tests for singleton validator instances."""

    def test_url_validator_singleton(self):
        """Test that url_validator is properly initialized."""
        assert isinstance(url_validator, URLValidator)
        assert url_validator.is_valid("https://youtube.com/watch?v=abc")

    def test_format_validator_singleton(self):
        """Test that format_validator is properly initialized."""
        assert isinstance(format_validator, FormatValidator)
        assert format_validator.is_valid_format_id("22")

    def test_parameter_validator_singleton(self):
        """Test that parameter_validator is properly initialized."""
        assert isinstance(parameter_validator, ParameterValidator)
        result = parameter_validator.validate_audio_format("mp3")
        assert result.is_valid


class TestAudioEnums:
    """Tests for audio format and quality enums."""

    def test_audio_format_values(self):
        """Test AudioFormat enum values."""
        assert AudioFormat.MP3.value == "mp3"
        assert AudioFormat.M4A.value == "m4a"
        assert AudioFormat.WAV.value == "wav"
        assert AudioFormat.OPUS.value == "opus"

    def test_audio_quality_values(self):
        """Test AudioQuality enum values."""
        assert AudioQuality.LOW.value == "128"
        assert AudioQuality.MEDIUM.value == "192"
        assert AudioQuality.HIGH.value == "320"

    def test_audio_format_from_string(self):
        """Test creating AudioFormat from string."""
        assert AudioFormat("mp3") == AudioFormat.MP3
        with pytest.raises(ValueError):
            AudioFormat("invalid")

    def test_audio_quality_from_string(self):
        """Test creating AudioQuality from string."""
        assert AudioQuality("128") == AudioQuality.LOW
        with pytest.raises(ValueError):
            AudioQuality("64")
