"""Template processor for output file naming.

This module provides secure template processing for downloaded file names,
with path traversal prevention and filename sanitization.
"""

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, FrozenSet, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class TemplateResult:
    """Result of template processing."""

    is_valid: bool
    processed_path: Optional[str] = None
    error_message: Optional[str] = None


class TemplateProcessor:
    """Processes output templates with security checks."""

    # Characters illegal in filenames on Windows/Linux/Mac
    ILLEGAL_CHARS: FrozenSet[str] = frozenset('<>:"/\\|?*')

    # Control characters (ASCII 0-31)
    CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x1f]")

    # Path traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",  # Unix parent directory
        r"\.\.\\",  # Windows parent directory
        r"^\.\.$",  # Just ".."
    ]

    # Default output template (yt-dlp style)
    DEFAULT_TEMPLATE = "%(title)s-%(id)s.%(ext)s"

    # Maximum filename length (filesystem limit is typically 255)
    MAX_FILENAME_LENGTH = 200

    # Reserved filenames on Windows
    WINDOWS_RESERVED: FrozenSet[str] = frozenset(
        {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            "COM1",
            "COM2",
            "COM3",
            "COM4",
            "COM5",
            "COM6",
            "COM7",
            "COM8",
            "COM9",
            "LPT1",
            "LPT2",
            "LPT3",
            "LPT4",
            "LPT5",
            "LPT6",
            "LPT7",
            "LPT8",
            "LPT9",
        }
    )

    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize template processor.

        Args:
            output_dir: Base output directory for downloads
        """
        self.output_dir = output_dir or "/app/downloads"

    def sanitize_filename(self, filename: str) -> str:  # noqa: C901
        """
        Sanitize a filename by removing/replacing illegal characters.

        Args:
            filename: Raw filename to sanitize

        Returns:
            Sanitized filename safe for filesystem use
        """
        # Save original filename for logging
        original_filename = filename

        if not filename:
            return "unnamed"

        # Normalize Unicode characters (NFKC normalization)
        filename = unicodedata.normalize("NFKC", filename)

        # Remove control characters
        filename = self.CONTROL_CHAR_PATTERN.sub("", filename)

        # Remove null bytes (security issue)
        filename = filename.replace("\x00", "")

        # Replace illegal characters with underscore
        for char in self.ILLEGAL_CHARS:
            filename = filename.replace(char, "_")

        # Remove leading/trailing whitespace and dots
        filename = filename.strip().strip(".")

        # Handle Windows reserved names
        name_without_ext = filename.rsplit(".", 1)[0] if "." in filename else filename
        if name_without_ext.upper() in self.WINDOWS_RESERVED:
            filename = f"_{filename}"

        # Truncate if too long (preserve extension)
        if len(filename) > self.MAX_FILENAME_LENGTH:
            if "." in filename:
                name, ext = filename.rsplit(".", 1)
                max_name_len = self.MAX_FILENAME_LENGTH - len(ext) - 1

                # If extension alone exceeds limit, truncate extension too
                if max_name_len < 1:
                    # Extension is too long, truncate both name and extension
                    # Reserve at least 1 char for name, 1 char for extension, 1 for dot
                    max_ext_len = min(len(ext), self.MAX_FILENAME_LENGTH - 2)
                    max_name_len = self.MAX_FILENAME_LENGTH - max_ext_len - 1
                    ext = ext[:max_ext_len]

                # Ensure name is not empty (at least 1 character)
                if max_name_len < 1:
                    max_name_len = 1

                filename = f"{name[:max_name_len]}.{ext}"
            else:
                filename = filename[: self.MAX_FILENAME_LENGTH]

            # Re-check Windows reserved names after truncation
            # Truncation might create a reserved name (e.g., "AUXabc" -> "AUX")
            name_without_ext = filename.rsplit(".", 1)[0] if "." in filename else filename
            if name_without_ext.upper() in self.WINDOWS_RESERVED:
                filename = f"_{filename}"
                # If this makes it too long, truncate again (preserving the underscore)
                if len(filename) > self.MAX_FILENAME_LENGTH:
                    filename = filename[: self.MAX_FILENAME_LENGTH]

        # Ensure we have a valid filename
        if not filename or filename in (".", ".."):
            filename = "unnamed"

        logger.debug("Filename sanitized", original=original_filename, result=filename)
        return filename

    def validate_template(self, template: str) -> TemplateResult:
        """
        Validate an output template for security issues.

        Args:
            template: yt-dlp style output template

        Returns:
            TemplateResult with validation status
        """
        if not template or not isinstance(template, str):
            return TemplateResult(
                is_valid=False, error_message="Template is required and must be a string"
            )

        template = template.strip()
        if not template:
            return TemplateResult(is_valid=False, error_message="Template cannot be empty")

        # Check for path traversal attempts
        for pattern in self.PATH_TRAVERSAL_PATTERNS:
            if re.search(pattern, template):
                logger.warning("Path traversal detected in template", template=template)
                return TemplateResult(
                    is_valid=False,
                    error_message="Template contains path traversal sequences",
                )

        # Check for absolute paths
        if template.startswith("/") or (
            len(template) > 1 and template[1] == ":" and template[0].isalpha()
        ):
            logger.warning("Absolute path detected in template", template=template)
            return TemplateResult(
                is_valid=False, error_message="Template cannot use absolute paths"
            )

        # Check for null bytes
        if "\x00" in template:
            logger.warning("Null byte detected in template", template=template)
            return TemplateResult(
                is_valid=False, error_message="Template contains invalid characters"
            )

        return TemplateResult(is_valid=True, processed_path=template)

    def validate_output_path(self, path: str) -> TemplateResult:
        """
        Validate that an output path is within the allowed directory.

        Args:
            path: Output file path to validate

        Returns:
            TemplateResult with validation status
        """
        if not path:
            return TemplateResult(is_valid=False, error_message="Path is required")

        try:
            # Resolve the path to catch symbolic links and normalize
            resolved_path = Path(path).resolve()
            output_dir = Path(self.output_dir).resolve()

            # Check if path is within output directory
            try:
                resolved_path.relative_to(output_dir)
            except ValueError:
                logger.warning(
                    "Path outside output directory",
                    path=str(resolved_path),
                    output_dir=str(output_dir),
                )
                return TemplateResult(
                    is_valid=False,
                    error_message="Output path must be within the configured output directory",
                )

            return TemplateResult(is_valid=True, processed_path=str(resolved_path))

        except (ValueError, FileNotFoundError, RuntimeError) as e:
            logger.warning("Path validation failed", path=path, error=str(e))
            return TemplateResult(is_valid=False, error_message="Invalid path format")

    def process_template(self, template: str, variables: Dict[str, str]) -> TemplateResult:
        """
        Process a template with variable substitution.

        This is a simplified processor that handles basic %(var)s patterns.
        For full yt-dlp template support, use yt-dlp's native processing.

        Args:
            template: yt-dlp style template string
            variables: Dictionary of variable values

        Returns:
            TemplateResult with processed filename
        """
        # Validate template first
        validation = self.validate_template(template)
        if not validation.is_valid:
            return validation

        try:
            # Use Python's % formatting for yt-dlp style templates
            processed = template % variables
        except KeyError as e:
            return TemplateResult(is_valid=False, error_message=f"Missing template variable: {e}")
        except ValueError as e:
            return TemplateResult(is_valid=False, error_message=f"Invalid template format: {e}")
        except TypeError as e:
            return TemplateResult(
                is_valid=False,
                error_message=f"Type mismatch in template variable: {e}",
            )

        # Sanitize the result
        processed = self.sanitize_filename(processed)

        return TemplateResult(is_valid=True, processed_path=processed)

    def get_unique_filename(self, directory: str, filename: str) -> str:
        """
        Generate a unique filename by adding numeric suffix if file exists.

        Args:
            directory: Directory path
            filename: Desired filename

        Returns:
            Unique filename (may have numeric suffix)
        """
        if not filename:
            filename = "unnamed"

        full_path = Path(directory) / filename

        if not full_path.exists():
            return filename

        # Split filename and extension
        if "." in filename:
            name, ext = filename.rsplit(".", 1)
            ext = f".{ext}"
        else:
            name = filename
            ext = ""

        # Find unique name with numeric suffix
        counter = 1
        while True:
            new_filename = f"{name}_{counter}{ext}"
            new_path = Path(directory) / new_filename

            if not new_path.exists():
                logger.debug(
                    "Generated unique filename",
                    original=filename,
                    unique=new_filename,
                )
                return new_filename

            counter += 1

            # Safety limit
            if counter > 10000:
                logger.error("Could not generate unique filename", filename=filename)
                raise ValueError(f"Could not generate unique filename after {counter} attempts")

    def build_output_path(
        self,
        template: Optional[str],
        variables: Dict[str, str],
        ensure_unique: bool = True,
    ) -> TemplateResult:
        """
        Build a complete output path from template and variables.

        Args:
            template: Output template (uses default if None)
            variables: Template variables
            ensure_unique: Whether to ensure unique filename

        Returns:
            TemplateResult with full output path
        """
        # Use default template if not provided
        if not template:
            template = self.DEFAULT_TEMPLATE

        # Process template
        result = self.process_template(template, variables)
        if not result.is_valid or result.processed_path is None:
            return result

        filename: str = result.processed_path

        # Ensure unique filename if requested
        if ensure_unique:
            try:
                filename = self.get_unique_filename(self.output_dir, filename)
            except ValueError as e:
                return TemplateResult(is_valid=False, error_message=str(e))

        # Build full path
        full_path = str(Path(self.output_dir) / filename)

        # Validate the final path
        path_validation = self.validate_output_path(full_path)
        if not path_validation.is_valid:
            return path_validation

        return TemplateResult(is_valid=True, processed_path=full_path)


# Singleton instance for convenience
template_processor = TemplateProcessor()


def sanitize_filename(filename: str) -> str:
    """
    Convenience function to sanitize a filename.

    Args:
        filename: Raw filename

    Returns:
        Sanitized filename
    """
    return template_processor.sanitize_filename(filename)


def validate_template(template: str) -> bool:
    """
    Convenience function to validate a template.

    Args:
        template: Template string

    Returns:
        True if template is valid
    """
    return template_processor.validate_template(template).is_valid
