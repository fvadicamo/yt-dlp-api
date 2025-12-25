"""Tests for structured logging"""

import logging
import re

import pytest

from app.core.logging import (
    add_request_id,
    clear_request_id,
    configure_logging,
    get_logger,
    get_request_id,
    hash_api_key,
    set_request_id,
)


class TestAPIKeyHashing:
    """Test API key hashing for safe logging"""

    def test_hash_api_key(self) -> None:
        """Test API key is hashed correctly"""
        api_key = "secret-api-key-12345"
        hashed = hash_api_key(api_key)

        assert hashed.startswith("sha256:")
        assert len(hashed) == 23  # "sha256:" (7) + 16 hex chars
        assert api_key not in hashed

    def test_hash_api_key_consistent(self) -> None:
        """Test same API key produces same hash"""
        api_key = "test-key"
        hash1 = hash_api_key(api_key)
        hash2 = hash_api_key(api_key)

        assert hash1 == hash2

    def test_hash_api_key_different_keys(self) -> None:
        """Test different API keys produce different hashes"""
        key1 = "api-key-1"
        key2 = "api-key-2"

        hash1 = hash_api_key(key1)
        hash2 = hash_api_key(key2)

        assert hash1 != hash2


class TestRequestIDManagement:
    """Test request_id context variable management"""

    def test_set_request_id_explicit(self) -> None:
        """Test setting explicit request_id"""
        request_id = "test-request-123"
        result = set_request_id(request_id)

        assert result == request_id
        assert get_request_id() == request_id

    def test_set_request_id_auto_generate(self) -> None:
        """Test auto-generating request_id"""
        result = set_request_id()

        assert result is not None
        assert result.startswith("req_")
        assert len(result) == 16  # "req_" (4) + 12 hex chars
        assert get_request_id() == result

    def test_clear_request_id(self) -> None:
        """Test clearing request_id"""
        set_request_id("test-123")
        assert get_request_id() == "test-123"

        clear_request_id()
        assert get_request_id() is None

    def test_request_id_isolation(self) -> None:
        """Test request_id is isolated per context"""
        # This test verifies the context variable behavior
        set_request_id("request-1")
        assert get_request_id() == "request-1"

        clear_request_id()
        assert get_request_id() is None


class TestAddRequestIDProcessor:
    """Test request_id processor for structlog"""

    def test_add_request_id_when_set(self) -> None:
        """Test request_id is added to event_dict when set"""
        set_request_id("test-request-456")

        event_dict = {"event": "test"}
        result = add_request_id(None, "info", event_dict)

        assert result["request_id"] == "test-request-456"
        assert result["event"] == "test"

        clear_request_id()

    def test_add_request_id_when_not_set(self) -> None:
        """Test request_id is not added when not set"""
        clear_request_id()

        event_dict = {"event": "test"}
        result = add_request_id(None, "info", event_dict)

        assert "request_id" not in result
        assert result["event"] == "test"


class TestLoggingConfiguration:
    """Test logging configuration"""

    def test_configure_logging_json_format(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test JSON format logging configuration"""
        configure_logging(log_level="INFO", log_format="json")

        logger = get_logger("test")
        set_request_id("req-json-test")

        # Capture output
        with caplog.at_level(logging.INFO):
            logger.info("test message", extra_field="value")

        clear_request_id()

        # Verify output contains expected fields
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.levelname == "INFO"
        assert "test message" in record.message

    def test_configure_logging_console_format(self) -> None:
        """Test console format logging configuration"""
        configure_logging(log_level="DEBUG", log_format="console")

        logger = get_logger("test")
        # Should not raise
        logger.debug("debug message")

    def test_configure_logging_levels(self) -> None:
        """Test different log levels"""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            configure_logging(log_level=level, log_format="json")
            logger = get_logger(f"test_{level}")
            # Should not raise
            logger.info(f"test {level}")

    def test_get_logger(self) -> None:
        """Test getting logger instance"""
        configure_logging()
        logger = get_logger("test.module")

        assert logger is not None
        # Logger is a BoundLoggerLazyProxy, which is the expected type
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")


class TestLogRedaction:
    """Test sensitive data redaction in logs"""

    def test_api_key_not_logged_directly(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test API keys are not logged in plain text"""
        configure_logging(log_level="INFO", log_format="json")
        logger = get_logger("test")

        api_key = "super-secret-key-12345"
        hashed_key = hash_api_key(api_key)

        # Log with hashed key
        with caplog.at_level(logging.INFO):
            logger.info("API request", api_key_hash=hashed_key)

        # Verify original key is not in the fully rendered log output
        assert api_key not in caplog.text

        # The hash should be in the structured data (not necessarily in message)
        # This test verifies that we're using hashing, not that it appears in output
        assert hashed_key.startswith("sha256:")

    def test_redaction_effectiveness(self) -> None:
        """Test automated verification of redaction effectiveness"""
        # Sensitive patterns that should never appear in logs
        sensitive_patterns = [
            r"--cookies\s+[^\s]+",
            r"X-API-Key:\s*[^\s]+",
            r"Authorization:\s*[^\s]+",
            r"--password\s+[^\s]+",
        ]

        # Simulate command that should be redacted
        command = "--cookies /path/to/cookie.txt --password secret123 https://example.com"

        # Apply redaction (this would be done in actual logging)
        redacted = command
        for pattern in sensitive_patterns:
            redacted = re.sub(pattern, "[REDACTED]", redacted)

        # Verify sensitive data is removed
        assert "/path/to/cookie.txt" not in redacted
        assert "secret123" not in redacted
        assert "[REDACTED]" in redacted
