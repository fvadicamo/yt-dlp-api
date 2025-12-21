"""Request and response schemas for API endpoints.

This module provides Pydantic models for API request validation
and response serialization.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.validation import AudioFormat


class VideoInfoRequest(BaseModel):
    """Query parameters for video info endpoint."""

    url: str = Field(..., description="Video URL")
    include_formats: bool = Field(False, description="Include available formats")
    include_subtitles: bool = Field(False, description="Include available subtitles")


class VideoFormatResponse(BaseModel):
    """Video format information."""

    format_id: str
    ext: str
    resolution: Optional[str] = None
    audio_bitrate: Optional[int] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    filesize: Optional[int] = None
    format_type: str = "video+audio"


class SubtitleResponse(BaseModel):
    """Subtitle information."""

    language: str
    format: str
    auto_generated: bool


class VideoInfoResponse(BaseModel):
    """Video metadata response."""

    video_id: str
    title: str
    duration: int
    author: str
    upload_date: str
    view_count: int
    thumbnail_url: str
    description: str
    formats: Optional[List[VideoFormatResponse]] = None
    subtitles: Optional[List[SubtitleResponse]] = None


class FormatsResponse(BaseModel):
    """Response for formats endpoint."""

    formats: List[VideoFormatResponse]
    video_audio: List[VideoFormatResponse] = Field(
        default_factory=list, description="Formats with video and audio"
    )
    video_only: List[VideoFormatResponse] = Field(
        default_factory=list, description="Video-only formats"
    )
    audio_only: List[VideoFormatResponse] = Field(
        default_factory=list, description="Audio-only formats"
    )


class DownloadRequest(BaseModel):
    """Request body for download endpoint."""

    url: str = Field(..., description="Video URL to download")
    format_id: Optional[str] = Field(None, description="Format ID to download")
    output_template: Optional[str] = Field(None, description="Output filename template")
    extract_audio: bool = Field(False, description="Extract audio only")
    audio_format: Optional[str] = Field(None, description="Audio format (mp3, m4a, wav, opus)")
    include_subtitles: bool = Field(False, description="Download subtitles")
    subtitle_lang: Optional[str] = Field(None, description="Subtitle language (ISO 639)")
    async_mode: bool = Field(
        True,
        alias="async",
        description="Async mode returns job_id immediately. Sync mode waits for completion.",
    )

    @field_validator("audio_format")
    @classmethod
    def validate_audio_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate audio format if provided."""
        if v is None:
            return v
        try:
            AudioFormat(v.lower())
            return v.lower()
        except ValueError as e:
            valid = [f.value for f in AudioFormat]
            raise ValueError(f"Invalid audio format. Valid options: {', '.join(valid)}") from e


class DownloadResponse(BaseModel):
    """Response for async download."""

    job_id: str
    status: str
    created_at: str
    queue_position: Optional[int] = None
    message: str = "Download job created"


class SyncDownloadResponse(BaseModel):
    """Response for sync download."""

    file_path: str
    file_size: int
    duration: float
    format_id: str


class JobStatusResponse(BaseModel):
    """Response for job status endpoint."""

    job_id: str
    status: str
    url: str
    progress: int
    retry_count: int
    error_message: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    duration: Optional[float] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    queue_position: Optional[int] = None


class ComponentHealth(BaseModel):
    """Health status of a single component."""

    status: Literal["healthy", "unhealthy"]
    version: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    """Detailed health check response."""

    status: Literal["healthy", "unhealthy"]
    timestamp: str
    version: str
    uptime_seconds: float
    components: Dict[str, ComponentHealth]


class LivenessResponse(BaseModel):
    """Simple liveness check response."""

    status: Literal["alive"]


class ReadinessResponse(BaseModel):
    """Readiness check response."""

    status: Literal["ready", "not_ready"]
    ready: bool
    message: Optional[str] = None


class ErrorDetail(BaseModel):
    """Structured error response."""

    error_code: str
    message: str
    details: Optional[str] = None
    timestamp: str
    request_id: Optional[str] = None
    suggestion: Optional[str] = None
