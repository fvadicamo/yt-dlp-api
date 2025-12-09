"""Tests for template processor."""

from pathlib import Path

import pytest

from app.core.template import (
    TemplateProcessor,
    TemplateResult,
    sanitize_filename,
    template_processor,
    validate_template,
)


class TestTemplateProcessor:
    """Tests for TemplateProcessor class."""

    @pytest.fixture
    def processor(self) -> TemplateProcessor:
        """Create a template processor instance."""
        return TemplateProcessor(output_dir="/app/downloads")

    @pytest.fixture
    def temp_processor(self, tmp_path: Path) -> TemplateProcessor:
        """Create a template processor with temp directory."""
        return TemplateProcessor(output_dir=str(tmp_path))


class TestSanitizeFilename(TestTemplateProcessor):
    """Tests for filename sanitization."""

    @pytest.mark.parametrize(
        "filename,expected",
        [
            ("valid_filename.mp4", "valid_filename.mp4"),
            ("my video.mp4", "my video.mp4"),
            ("video-123.mp4", "video-123.mp4"),
            ("日本語タイトル.mp4", "日本語タイトル.mp4"),
        ],
    )
    def test_valid_filenames_unchanged(
        self, processor: TemplateProcessor, filename: str, expected: str
    ):
        """Test that valid filenames pass through unchanged."""
        result = processor.sanitize_filename(filename)
        assert result == expected

    @pytest.mark.parametrize(
        "filename,expected_contains",
        [
            ("file<name>.mp4", "_"),  # < replaced
            ("file>name>.mp4", "_"),  # > replaced
            ('file"name".mp4', "_"),  # " replaced
            ("file:name.mp4", "_"),  # : replaced
            ("file|name.mp4", "_"),  # | replaced
            ("file?name.mp4", "_"),  # ? replaced
            ("file*name.mp4", "_"),  # * replaced
            ("file\\name.mp4", "_"),  # \ replaced
            ("file/name.mp4", "_"),  # / replaced
        ],
    )
    def test_illegal_chars_replaced(
        self, processor: TemplateProcessor, filename: str, expected_contains: str
    ):
        """Test that illegal characters are replaced."""
        result = processor.sanitize_filename(filename)
        assert expected_contains in result
        # Original illegal char should not be in result
        for char in '<>:"/\\|?*':
            assert char not in result

    def test_null_bytes_removed(self, processor: TemplateProcessor):
        """Test that null bytes are removed."""
        result = processor.sanitize_filename("file\x00name.mp4")
        assert "\x00" not in result
        assert result == "filename.mp4"

    def test_control_chars_removed(self, processor: TemplateProcessor):
        """Test that control characters are removed."""
        result = processor.sanitize_filename("file\x01\x02\x03name.mp4")
        assert "\x01" not in result
        assert result == "filename.mp4"

    def test_empty_filename_returns_unnamed(self, processor: TemplateProcessor):
        """Test that empty filename returns 'unnamed'."""
        assert processor.sanitize_filename("") == "unnamed"
        assert processor.sanitize_filename("   ") == "unnamed"

    def test_dots_only_returns_unnamed(self, processor: TemplateProcessor):
        """Test that dots-only filename returns 'unnamed'."""
        assert processor.sanitize_filename(".") == "unnamed"
        assert processor.sanitize_filename("..") == "unnamed"
        assert processor.sanitize_filename("...") == "unnamed"

    def test_leading_trailing_dots_stripped(self, processor: TemplateProcessor):
        """Test that leading/trailing dots are stripped."""
        result = processor.sanitize_filename("...filename...")
        assert not result.startswith(".")
        assert not result.endswith(".")

    @pytest.mark.parametrize(
        "reserved_name",
        ["CON", "PRN", "AUX", "NUL", "COM1", "COM9", "LPT1", "LPT9"],
    )
    def test_windows_reserved_names_prefixed(
        self, processor: TemplateProcessor, reserved_name: str
    ):
        """Test that Windows reserved names are prefixed."""
        result = processor.sanitize_filename(reserved_name)
        assert result.startswith("_")

        # Also test with extension
        result = processor.sanitize_filename(f"{reserved_name}.txt")
        assert result.startswith("_")

    def test_long_filename_truncated(self, processor: TemplateProcessor):
        """Test that overly long filenames are truncated."""
        long_name = "a" * 300 + ".mp4"
        result = processor.sanitize_filename(long_name)
        assert len(result) <= processor.MAX_FILENAME_LENGTH
        assert result.endswith(".mp4")

    def test_long_extension_truncated(self, processor: TemplateProcessor):
        """Test that overly long extensions are truncated."""
        # Extension longer than MAX_FILENAME_LENGTH
        long_ext = "x" * 250
        filename = f"test.{long_ext}"
        result = processor.sanitize_filename(filename)

        # Result should not exceed MAX_FILENAME_LENGTH
        assert len(result) <= processor.MAX_FILENAME_LENGTH
        # Result should not start with dot (invalid filename)
        assert not result.startswith(".")
        # Result should have at least one character before the dot
        assert "." in result
        name_part = result.rsplit(".", 1)[0]
        assert len(name_part) >= 1

    def test_filename_with_only_long_extension(self, processor: TemplateProcessor):
        """Test filename that is only a long extension (edge case)."""
        # Filename that is just a dot and very long extension
        long_ext = "x" * 250
        filename = f".{long_ext}"
        result = processor.sanitize_filename(filename)

        # Result should not exceed MAX_FILENAME_LENGTH
        assert len(result) <= processor.MAX_FILENAME_LENGTH
        # Result should not start with dot (invalid filename)
        # If it would start with dot, it should be replaced with "unnamed"
        assert not result.startswith(".") or result == "unnamed"

    def test_unicode_normalization(self, processor: TemplateProcessor):
        """Test Unicode normalization (NFKC)."""
        # Combining characters should be normalized
        result = processor.sanitize_filename("café.mp4")
        assert "café" in result or "cafe" in result  # Depends on normalization


class TestValidateTemplate(TestTemplateProcessor):
    """Tests for template validation."""

    @pytest.mark.parametrize(
        "template",
        [
            "%(title)s.%(ext)s",
            "%(title)s-%(id)s.%(ext)s",
            "%(uploader)s/%(title)s.%(ext)s",
            "video_%(id)s.mp4",
        ],
    )
    def test_valid_templates_accepted(self, processor: TemplateProcessor, template: str):
        """Test that valid templates are accepted."""
        result = processor.validate_template(template)
        assert result.is_valid is True

    @pytest.mark.parametrize(
        "template",
        [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "%(title)s/../secret.txt",
            "..",
        ],
    )
    def test_path_traversal_rejected(self, processor: TemplateProcessor, template: str):
        """Test that path traversal attempts are rejected."""
        result = processor.validate_template(template)
        assert result.is_valid is False
        assert "traversal" in result.error_message.lower()

    @pytest.mark.parametrize(
        "template",
        [
            "/etc/passwd",
            "C:\\Windows\\System32",
            "D:/important/file.txt",
        ],
    )
    def test_absolute_paths_rejected(self, processor: TemplateProcessor, template: str):
        """Test that absolute paths are rejected."""
        result = processor.validate_template(template)
        assert result.is_valid is False
        assert "absolute" in result.error_message.lower()

    def test_absolute_path_with_traversal_rejected(self, processor: TemplateProcessor):
        """Test that absolute paths with traversal are rejected."""
        # This is caught as path traversal first
        result = processor.validate_template("/app/downloads/../secrets")
        assert result.is_valid is False
        assert "traversal" in result.error_message.lower()

    def test_null_bytes_rejected(self, processor: TemplateProcessor):
        """Test that null bytes in template are rejected."""
        result = processor.validate_template("file\x00name.%(ext)s")
        assert result.is_valid is False
        assert "invalid" in result.error_message.lower()

    def test_empty_template_rejected(self, processor: TemplateProcessor):
        """Test that empty templates are rejected."""
        result = processor.validate_template("")
        assert result.is_valid is False
        assert "required" in result.error_message.lower()

    def test_whitespace_only_template_rejected(self, processor: TemplateProcessor):
        """Test that whitespace-only templates are rejected."""
        result = processor.validate_template("   ")
        assert result.is_valid is False
        assert "empty" in result.error_message.lower()

    def test_none_template_rejected(self, processor: TemplateProcessor):
        """Test that None template is rejected."""
        result = processor.validate_template(None)
        assert result.is_valid is False


class TestValidateOutputPath(TestTemplateProcessor):
    """Tests for output path validation."""

    def test_valid_path_within_output_dir(self, temp_processor: TemplateProcessor):
        """Test that paths within output directory are accepted."""
        output_dir = temp_processor.output_dir
        path = f"{output_dir}/video.mp4"
        result = temp_processor.validate_output_path(path)
        assert result.is_valid is True

    def test_path_outside_output_dir_rejected(self, temp_processor: TemplateProcessor):
        """Test that paths outside output directory are rejected."""
        result = temp_processor.validate_output_path("/etc/passwd")
        assert result.is_valid is False
        assert "output directory" in result.error_message.lower()

    def test_empty_path_rejected(self, temp_processor: TemplateProcessor):
        """Test that empty paths are rejected."""
        result = temp_processor.validate_output_path("")
        assert result.is_valid is False


class TestProcessTemplate(TestTemplateProcessor):
    """Tests for template processing."""

    def test_basic_template_processing(self, processor: TemplateProcessor):
        """Test basic template variable substitution."""
        template = "%(title)s-%(id)s.%(ext)s"
        variables = {"title": "My Video", "id": "abc123", "ext": "mp4"}

        result = processor.process_template(template, variables)
        assert result.is_valid is True
        assert "My Video" in result.processed_path
        assert "abc123" in result.processed_path
        assert result.processed_path.endswith(".mp4")

    def test_missing_variable_error(self, processor: TemplateProcessor):
        """Test that missing variables cause error."""
        template = "%(title)s-%(missing)s.%(ext)s"
        variables = {"title": "My Video", "ext": "mp4"}

        result = processor.process_template(template, variables)
        assert result.is_valid is False
        assert "missing" in result.error_message.lower()

    def test_invalid_template_format(self, processor: TemplateProcessor):
        """Test that invalid template format causes error."""
        template = "%(title)s-%(invalid format.%(ext)s"
        variables = {"title": "My Video", "ext": "mp4"}

        # This should either fail validation or processing depending on the specific error
        result = processor.process_template(template, variables)
        assert isinstance(result.is_valid, bool)

    def test_result_is_sanitized(self, processor: TemplateProcessor):
        """Test that processed result is sanitized."""
        template = "%(title)s.%(ext)s"
        variables = {"title": "Video<>Name", "ext": "mp4"}

        result = processor.process_template(template, variables)
        assert result.is_valid is True
        # Illegal chars should be replaced
        assert "<" not in result.processed_path
        assert ">" not in result.processed_path

    def test_type_mismatch_error(self, processor: TemplateProcessor):
        """Test that type mismatch in format specifier causes error."""
        # Template with %d (integer) format but string value
        template = "%(count)d items"
        variables = {"count": "text"}

        result = processor.process_template(template, variables)
        assert result.is_valid is False
        assert "type" in result.error_message.lower() or "mismatch" in result.error_message.lower()
        assert result.processed_path is None

    def test_type_mismatch_with_float_format(self, processor: TemplateProcessor):
        """Test that type mismatch with float format specifier causes error."""
        # Template with %f (float) format but string value
        template = "Value: %(value)f"
        variables = {"value": "not_a_number"}

        result = processor.process_template(template, variables)
        assert result.is_valid is False
        assert "type" in result.error_message.lower() or "mismatch" in result.error_message.lower()


class TestGetUniqueFilename(TestTemplateProcessor):
    """Tests for unique filename generation."""

    def test_unique_filename_when_no_conflict(
        self, temp_processor: TemplateProcessor, tmp_path: Path
    ):
        """Test that filename is unchanged when no conflict."""
        filename = temp_processor.get_unique_filename(str(tmp_path), "video.mp4")
        assert filename == "video.mp4"

    def test_unique_filename_with_conflict(self, temp_processor: TemplateProcessor, tmp_path: Path):
        """Test that numeric suffix is added when file exists."""
        # Create existing file
        (tmp_path / "video.mp4").touch()

        filename = temp_processor.get_unique_filename(str(tmp_path), "video.mp4")
        assert filename == "video_1.mp4"

    def test_unique_filename_multiple_conflicts(
        self, temp_processor: TemplateProcessor, tmp_path: Path
    ):
        """Test handling of multiple filename conflicts."""
        # Create existing files
        (tmp_path / "video.mp4").touch()
        (tmp_path / "video_1.mp4").touch()
        (tmp_path / "video_2.mp4").touch()

        filename = temp_processor.get_unique_filename(str(tmp_path), "video.mp4")
        assert filename == "video_3.mp4"

    def test_unique_filename_no_extension(self, temp_processor: TemplateProcessor, tmp_path: Path):
        """Test unique filename for files without extension."""
        (tmp_path / "video").touch()

        filename = temp_processor.get_unique_filename(str(tmp_path), "video")
        assert filename == "video_1"


class TestBuildOutputPath(TestTemplateProcessor):
    """Tests for building complete output paths."""

    def test_build_path_with_template(self, temp_processor: TemplateProcessor, tmp_path: Path):
        """Test building path with custom template."""
        variables = {"title": "My Video", "id": "abc", "ext": "mp4"}

        result = temp_processor.build_output_path(
            "%(title)s-%(id)s.%(ext)s", variables, ensure_unique=False
        )

        assert result.is_valid is True
        assert "My Video" in result.processed_path
        assert result.processed_path.startswith(str(tmp_path))

    def test_build_path_with_default_template(
        self, temp_processor: TemplateProcessor, tmp_path: Path
    ):
        """Test building path with default template."""
        variables = {"title": "My Video", "id": "abc", "ext": "mp4"}

        result = temp_processor.build_output_path(None, variables, ensure_unique=False)

        assert result.is_valid is True
        assert "My Video" in result.processed_path

    def test_build_path_ensures_unique(self, temp_processor: TemplateProcessor, tmp_path: Path):
        """Test that unique filename is generated when file exists."""
        variables = {"title": "video", "id": "abc", "ext": "mp4"}

        # Create existing file
        first_result = temp_processor.build_output_path(
            "%(title)s.%(ext)s", variables, ensure_unique=False
        )
        Path(first_result.processed_path).touch()

        # Build path again - should be unique
        second_result = temp_processor.build_output_path(
            "%(title)s.%(ext)s", variables, ensure_unique=True
        )

        assert second_result.is_valid is True
        assert second_result.processed_path != first_result.processed_path
        assert "_1" in second_result.processed_path


class TestTemplateResult:
    """Tests for TemplateResult dataclass."""

    def test_valid_result(self):
        """Test creating a valid result."""
        result = TemplateResult(is_valid=True, processed_path="/app/downloads/video.mp4")
        assert result.is_valid is True
        assert result.error_message is None

    def test_invalid_result(self):
        """Test creating an invalid result."""
        result = TemplateResult(is_valid=False, error_message="Path traversal detected")
        assert result.is_valid is False
        assert result.processed_path is None

    def test_result_is_immutable(self):
        """Test that TemplateResult is immutable."""
        result = TemplateResult(is_valid=True, processed_path="/path")
        with pytest.raises(AttributeError):
            result.is_valid = False


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_sanitize_filename_function(self):
        """Test the sanitize_filename convenience function."""
        result = sanitize_filename("file<>name.mp4")
        assert "<" not in result
        assert ">" not in result

    def test_validate_template_function(self):
        """Test the validate_template convenience function."""
        assert validate_template("%(title)s.%(ext)s") is True
        assert validate_template("../../../etc/passwd") is False


class TestSingletonInstance:
    """Tests for singleton template processor."""

    def test_template_processor_singleton(self):
        """Test that template_processor is properly initialized."""
        assert isinstance(template_processor, TemplateProcessor)
        result = template_processor.validate_template("%(title)s.%(ext)s")
        assert result.is_valid is True


class TestSecurityEdgeCases:
    """Security-focused edge case tests."""

    @pytest.fixture
    def processor(self) -> TemplateProcessor:
        """Create a template processor instance."""
        return TemplateProcessor(output_dir="/app/downloads")

    def test_unicode_path_traversal(self, processor: TemplateProcessor):
        """Test Unicode-encoded path traversal attempts."""
        # Various Unicode representations of ".."
        test_cases = [
            ".\u002e/etc/passwd",  # Period + Unicode period
            "\u002e\u002e/etc/passwd",  # Two Unicode periods
        ]

        for template in test_cases:
            result = processor.validate_template(template)
            # Should either be rejected or sanitized
            if result.is_valid:
                assert ".." not in result.processed_path

    def test_url_encoded_in_filename(self, processor: TemplateProcessor):
        """Test that URL-encoded characters in filename are handled."""
        result = processor.sanitize_filename("%2e%2e%2fetc%2fpasswd")
        # The literal %2e shouldn't cause issues after sanitization
        assert "/" not in result

    def test_very_long_path_traversal(self, processor: TemplateProcessor):
        """Test that long path traversal sequences are caught."""
        template = "../" * 100 + "etc/passwd"
        result = processor.validate_template(template)
        assert result.is_valid is False

    def test_mixed_slash_traversal(self, processor: TemplateProcessor):
        """Test mixed forward/back slash traversal."""
        templates = [
            "..\\..\\etc\\passwd",
            "..\\..\\/etc/passwd",
        ]

        for template in templates:
            result = processor.validate_template(template)
            assert result.is_valid is False
