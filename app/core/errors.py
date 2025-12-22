"""Centralized error handling for the API.

This module provides standardized error codes, exception-to-response mapping,
and a global exception handler for FastAPI.

Implements Requirement 16: Standardized Error Responses.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Type

import structlog
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_503_SERVICE_UNAVAILABLE,
)

from app.core.logging import get_request_id
from app.providers.exceptions import (
    AuthenticationError,
    CookieError,
    DownloadError,
    FormatNotFoundError,
    InvalidURLError,
    ProviderError,
    TranscodingError,
    VideoUnavailableError,
)
from app.services.job_service import JobNotFoundError

logger = structlog.get_logger(__name__)


class ErrorCode:
    """Standardized error codes for API responses.

    These codes provide machine-readable identifiers for error conditions
    that clients can use to implement error handling logic.
    """

    # Client Errors (4xx)
    INVALID_URL = "INVALID_URL"
    INVALID_FORMAT = "INVALID_FORMAT"
    INVALID_TEMPLATE = "INVALID_TEMPLATE"
    FORMAT_NOT_FOUND = "FORMAT_NOT_FOUND"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    AUTH_FAILED = "AUTH_FAILED"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # Server Errors (5xx)
    VIDEO_UNAVAILABLE = "VIDEO_UNAVAILABLE"
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    TRANSCODING_FAILED = "TRANSCODING_FAILED"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"

    # Service Unavailable (503)
    MISSING_COOKIE = "MISSING_COOKIE"
    COOKIE_EXPIRED = "COOKIE_EXPIRED"
    STORAGE_FULL = "STORAGE_FULL"
    QUEUE_FULL = "QUEUE_FULL"
    NO_SLOTS_AVAILABLE = "NO_SLOTS_AVAILABLE"
    COMPONENT_UNAVAILABLE = "COMPONENT_UNAVAILABLE"


# Error code to HTTP status code mapping
ERROR_CODE_TO_STATUS: Dict[str, int] = {
    # 400 Bad Request
    ErrorCode.INVALID_URL: HTTP_400_BAD_REQUEST,
    ErrorCode.INVALID_FORMAT: HTTP_400_BAD_REQUEST,
    ErrorCode.INVALID_TEMPLATE: HTTP_400_BAD_REQUEST,
    ErrorCode.FORMAT_NOT_FOUND: HTTP_400_BAD_REQUEST,
    ErrorCode.FILE_TOO_LARGE: HTTP_400_BAD_REQUEST,
    # 401 Unauthorized
    ErrorCode.AUTH_FAILED: HTTP_401_UNAUTHORIZED,
    # 404 Not Found
    ErrorCode.JOB_NOT_FOUND: HTTP_404_NOT_FOUND,
    ErrorCode.VIDEO_UNAVAILABLE: HTTP_404_NOT_FOUND,
    # 429 Too Many Requests
    ErrorCode.RATE_LIMIT_EXCEEDED: HTTP_429_TOO_MANY_REQUESTS,
    # 500 Internal Server Error
    ErrorCode.DOWNLOAD_FAILED: HTTP_500_INTERNAL_SERVER_ERROR,
    ErrorCode.TRANSCODING_FAILED: HTTP_500_INTERNAL_SERVER_ERROR,
    ErrorCode.PROVIDER_ERROR: HTTP_500_INTERNAL_SERVER_ERROR,
    ErrorCode.INTERNAL_ERROR: HTTP_500_INTERNAL_SERVER_ERROR,
    # 503 Service Unavailable
    ErrorCode.MISSING_COOKIE: HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.COOKIE_EXPIRED: HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.STORAGE_FULL: HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.QUEUE_FULL: HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.NO_SLOTS_AVAILABLE: HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.COMPONENT_UNAVAILABLE: HTTP_503_SERVICE_UNAVAILABLE,
}


# User-friendly suggestions for error resolution
ERROR_SUGGESTIONS: Dict[str, str] = {
    ErrorCode.INVALID_URL: (
        "Verify the URL format and ensure it's from a supported domain " "(youtube.com, youtu.be)"
    ),
    ErrorCode.INVALID_FORMAT: "Check the format ID is valid (e.g., '22', '140', 'bestvideo+bestaudio')",
    ErrorCode.INVALID_TEMPLATE: (
        "Check output template syntax. Avoid path traversal characters (../) "
        "and use valid placeholders like %(title)s"
    ),
    ErrorCode.FORMAT_NOT_FOUND: (
        "The requested format is not available. Use GET /api/v1/formats "
        "to list available formats"
    ),
    ErrorCode.FILE_TOO_LARGE: "The file exceeds the maximum allowed size. Try a lower quality format",
    ErrorCode.AUTH_FAILED: "Provide a valid API key in the X-API-Key header",
    ErrorCode.JOB_NOT_FOUND: "The job ID does not exist or has expired (TTL: 24 hours)",
    ErrorCode.RATE_LIMIT_EXCEEDED: "Wait for the Retry-After period before making more requests",
    ErrorCode.VIDEO_UNAVAILABLE: "The video may be private, deleted, age-restricted, or geo-blocked",
    ErrorCode.DOWNLOAD_FAILED: "The download operation failed. Check server logs for details",
    ErrorCode.TRANSCODING_FAILED: "Audio conversion failed. Try a different audio format",
    ErrorCode.PROVIDER_ERROR: "An error occurred with the video provider. Try again later",
    ErrorCode.INTERNAL_ERROR: "An unexpected error occurred. Contact administrator if the issue persists",
    ErrorCode.MISSING_COOKIE: "Cookie file not found. Contact administrator to configure authentication",
    ErrorCode.COOKIE_EXPIRED: (
        "Cookie authentication failed. Refresh the cookie file and use "
        "POST /api/v1/admin/reload-cookie"
    ),
    ErrorCode.STORAGE_FULL: "Insufficient disk space. Contact administrator to free up storage",
    ErrorCode.QUEUE_FULL: "Download queue is at capacity. Try again later",
    ErrorCode.NO_SLOTS_AVAILABLE: "All download slots are busy. Try again later",
    ErrorCode.COMPONENT_UNAVAILABLE: "A required system component is unavailable. Check /health for status",
}


# Exception type to error code mapping
# Order matters: subclasses must come before their base classes
EXCEPTION_TO_ERROR_CODE: Dict[Type[Exception], str] = {
    InvalidURLError: ErrorCode.INVALID_URL,
    VideoUnavailableError: ErrorCode.VIDEO_UNAVAILABLE,
    FormatNotFoundError: ErrorCode.FORMAT_NOT_FOUND,
    TranscodingError: ErrorCode.TRANSCODING_FAILED,
    AuthenticationError: ErrorCode.AUTH_FAILED,
    CookieError: ErrorCode.COOKIE_EXPIRED,
    DownloadError: ErrorCode.DOWNLOAD_FAILED,
    JobNotFoundError: ErrorCode.JOB_NOT_FOUND,
    # ProviderError must be last (after its subclasses)
    ProviderError: ErrorCode.PROVIDER_ERROR,
}


class APIError(Exception):
    """Structured API error that can be converted to ErrorDetail response.

    This exception class provides a standardized way to raise errors
    that will be converted to consistent error responses by the global
    exception handler.
    """

    def __init__(
        self,
        error_code: str,
        message: str,
        details: Optional[str] = None,
        suggestion: Optional[str] = None,
    ):
        """Initialize an API error.

        Args:
            error_code: Machine-readable error code from ErrorCode class.
            message: Human-readable error message.
            details: Optional additional details about the error.
            suggestion: Optional suggestion for resolution. If not provided,
                        the default suggestion for the error code is used.
        """
        self.error_code = error_code
        self.message = message
        self.details = details
        self.suggestion = suggestion or ERROR_SUGGESTIONS.get(error_code)
        super().__init__(message)


def map_exception_to_api_error(exc: Exception) -> APIError:
    """Map provider and service exceptions to APIError.

    Uses EXCEPTION_TO_ERROR_CODE dictionary for maintainable type-based dispatch.
    Dictionary order ensures subclasses are checked before their base classes.

    Args:
        exc: The exception to map.

    Returns:
        An APIError with the appropriate error code and message.
    """
    for exc_type, error_code in EXCEPTION_TO_ERROR_CODE.items():
        if isinstance(exc, exc_type):
            return APIError(error_code, str(exc))
    return APIError(ErrorCode.INTERNAL_ERROR, "An unexpected error occurred")


def _build_error_response(
    error_code: str,
    message: str,
    details: Optional[str] = None,
    suggestion: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a standardized error response dictionary.

    Args:
        error_code: Machine-readable error code.
        message: Human-readable error message.
        details: Optional additional details.
        suggestion: Optional suggestion for resolution.

    Returns:
        Dictionary matching the ErrorDetail schema.
    """
    request_id = get_request_id()
    timestamp = datetime.now(timezone.utc).isoformat()

    response: Dict[str, Any] = {
        "error_code": error_code,
        "message": message,
        "timestamp": timestamp,
    }

    if details:
        response["details"] = details
    if request_id:
        response["request_id"] = request_id
    if suggestion:
        response["suggestion"] = suggestion

    return response


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for FastAPI.

    Converts all exceptions to standardized ErrorDetail responses with
    consistent structure, proper HTTP status codes, and request tracing.

    Args:
        request: The FastAPI request object.
        exc: The exception that was raised.

    Returns:
        JSONResponse with ErrorDetail body and appropriate status code.
    """
    if isinstance(exc, APIError):
        # Already a structured API error
        status_code = ERROR_CODE_TO_STATUS.get(exc.error_code, HTTP_500_INTERNAL_SERVER_ERROR)
        response = _build_error_response(
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
            suggestion=exc.suggestion,
        )
        logger.warning(
            "api_error",
            error_code=exc.error_code,
            message=exc.message,
            path=request.url.path,
        )

    elif isinstance(exc, HTTPException):
        # FastAPI HTTPException - preserve status code
        status_code = exc.status_code

        # Check if detail is already structured
        if isinstance(exc.detail, dict) and "error_code" in exc.detail:
            error_code = exc.detail["error_code"]
            message = exc.detail.get("message", str(exc.detail))
            details = exc.detail.get("details")
        else:
            # Infer error code from status
            error_code = _status_to_error_code(status_code)
            message = str(exc.detail) if exc.detail else "An error occurred"
            details = None

        suggestion = ERROR_SUGGESTIONS.get(error_code)
        response = _build_error_response(
            error_code=error_code,
            message=message,
            details=details,
            suggestion=suggestion,
        )
        logger.warning(
            "http_exception",
            status_code=status_code,
            error_code=error_code,
            path=request.url.path,
        )

    elif isinstance(exc, (ProviderError, JobNotFoundError)):
        # Map provider/service exceptions
        api_error = map_exception_to_api_error(exc)
        status_code = ERROR_CODE_TO_STATUS.get(api_error.error_code, HTTP_500_INTERNAL_SERVER_ERROR)
        response = _build_error_response(
            error_code=api_error.error_code,
            message=api_error.message,
            details=api_error.details,
            suggestion=api_error.suggestion,
        )
        logger.warning(
            "provider_error",
            error_code=api_error.error_code,
            error_type=type(exc).__name__,
            message=str(exc),
            path=request.url.path,
        )

    else:
        # Unexpected error - log with full traceback
        status_code = HTTP_500_INTERNAL_SERVER_ERROR
        response = _build_error_response(
            error_code=ErrorCode.INTERNAL_ERROR,
            message="An unexpected error occurred",
            suggestion=ERROR_SUGGESTIONS.get(ErrorCode.INTERNAL_ERROR),
        )
        logger.error(
            "unhandled_exception",
            error_type=type(exc).__name__,
            error=str(exc),
            path=request.url.path,
            exc_info=True,
        )

    return JSONResponse(status_code=status_code, content=response)


def _status_to_error_code(status_code: int) -> str:
    """Infer error code from HTTP status code.

    Args:
        status_code: HTTP status code.

    Returns:
        Appropriate error code string.
    """
    if status_code == HTTP_400_BAD_REQUEST:
        return ErrorCode.INVALID_URL
    elif status_code == HTTP_401_UNAUTHORIZED:
        return ErrorCode.AUTH_FAILED
    elif status_code == HTTP_404_NOT_FOUND:
        return ErrorCode.JOB_NOT_FOUND
    elif status_code == HTTP_429_TOO_MANY_REQUESTS:
        return ErrorCode.RATE_LIMIT_EXCEEDED
    elif status_code == HTTP_503_SERVICE_UNAVAILABLE:
        return ErrorCode.COMPONENT_UNAVAILABLE
    else:
        return ErrorCode.INTERNAL_ERROR
