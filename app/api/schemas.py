"""Request and response schemas for API endpoints.

This module provides Pydantic models for API request validation
and response serialization with OpenAPI examples.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.validation import AudioFormat


class VideoInfoRequest(BaseModel):
    """Query parameters for video info endpoint."""

    url: str = Field(
        ..., description="Video URL", examples=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]
    )
    include_formats: bool = Field(False, description="Include available formats")
    include_subtitles: bool = Field(False, description="Include available subtitles")


class VideoFormatResponse(BaseModel):
    """Video format information."""

    format_id: str = Field(..., examples=["22"])
    ext: str = Field(..., examples=["mp4"])
    resolution: Optional[str] = Field(None, examples=["1280x720"])
    audio_bitrate: Optional[int] = Field(None, examples=[128])
    video_codec: Optional[str] = Field(None, examples=["avc1.64001F"])
    audio_codec: Optional[str] = Field(None, examples=["mp4a.40.2"])
    filesize: Optional[int] = Field(None, examples=[52428800])
    format_type: str = Field("video+audio", examples=["video+audio", "video-only", "audio-only"])


class SubtitleResponse(BaseModel):
    """Subtitle information."""

    language: str = Field(..., examples=["en"])
    format: str = Field(..., examples=["vtt"])
    auto_generated: bool = Field(..., examples=[False])


class VideoInfoResponse(BaseModel):
    """Video metadata response."""

    video_id: str = Field(..., examples=["dQw4w9WgXcQ"])
    title: str = Field(..., examples=["Rick Astley - Never Gonna Give You Up"])
    duration: int = Field(..., description="Duration in seconds", examples=[212])
    author: str = Field(..., examples=["Rick Astley"])
    upload_date: str = Field(..., examples=["20091025"])
    view_count: int = Field(..., examples=[1500000000])
    thumbnail_url: str = Field(
        ..., examples=["https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"]
    )
    description: str = Field(
        ..., examples=["Official music video for Rick Astley - Never Gonna Give You Up"]
    )
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

    url: str = Field(
        ...,
        description="Video URL to download",
        examples=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
    )
    format_id: Optional[str] = Field(
        None,
        description="Format ID to download (use /formats endpoint to list available)",
        examples=["22", "bestvideo+bestaudio"],
    )
    output_template: Optional[str] = Field(
        None,
        description="Output filename template using yt-dlp placeholders",
        examples=["%(title)s.%(ext)s"],
    )
    extract_audio: bool = Field(False, description="Extract audio only")
    audio_format: Optional[str] = Field(
        None,
        description="Audio format for extraction",
        examples=["mp3", "m4a", "wav", "opus"],
    )
    include_subtitles: bool = Field(False, description="Download subtitles")
    subtitle_lang: Optional[str] = Field(
        None,
        description="Subtitle language (ISO 639-1 code)",
        examples=["en", "es", "fr"],
    )
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
    """Response for async download (HTTP 202)."""

    job_id: str = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])
    status: str = Field(..., examples=["pending"])
    created_at: str = Field(..., examples=["2025-12-25T10:30:00Z"])
    queue_position: Optional[int] = Field(None, examples=[3])
    message: str = Field("Download job created", examples=["Download job created and queued"])


class SyncDownloadResponse(BaseModel):
    """Response for sync download (HTTP 200)."""

    file_path: str = Field(..., examples=["/downloads/Rick_Astley_-_Never_Gonna_Give_You_Up.mp4"])
    file_size: int = Field(..., description="File size in bytes", examples=[52428800])
    duration: float = Field(..., description="Download duration in seconds", examples=[45.2])
    format_id: str = Field(..., examples=["22"])


class JobStatusResponse(BaseModel):
    """Response for job status endpoint."""

    job_id: str = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])
    status: str = Field(
        ...,
        description="Job status",
        examples=["pending", "processing", "completed", "failed", "retrying"],
    )
    url: str = Field(..., examples=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"])
    progress: int = Field(..., description="Progress percentage (0-100)", examples=[75])
    retry_count: int = Field(..., examples=[0])
    error_message: Optional[str] = Field(None, examples=["Video unavailable"])
    file_path: Optional[str] = Field(None, examples=["/downloads/video.mp4"])
    file_size: Optional[int] = Field(None, examples=[52428800])
    duration: Optional[float] = Field(None, examples=[45.2])
    created_at: str = Field(..., examples=["2025-12-25T10:30:00Z"])
    started_at: Optional[str] = Field(None, examples=["2025-12-25T10:30:05Z"])
    completed_at: Optional[str] = Field(None, examples=["2025-12-25T10:31:00Z"])
    queue_position: Optional[int] = Field(None, examples=[3])


class ComponentHealth(BaseModel):
    """Health status of a single component."""

    status: Literal["healthy", "unhealthy"] = Field(..., examples=["healthy"])
    version: Optional[str] = Field(default=None, examples=["2024.12.01"])
    details: Optional[Dict[str, Any]] = Field(default=None, examples=[{"latency_ms": 150}])


class HealthResponse(BaseModel):
    """Detailed health check response."""

    status: Literal["healthy", "unhealthy"] = Field(..., examples=["healthy"])
    timestamp: str = Field(..., examples=["2025-12-25T10:30:00Z"])
    version: str = Field(..., examples=["1.0.0"])
    uptime_seconds: float = Field(..., examples=[3600.5])
    components: Dict[str, ComponentHealth]


class LivenessResponse(BaseModel):
    """Simple liveness check response for container orchestration."""

    status: Literal["alive"] = Field(..., examples=["alive"])


class ReadinessResponse(BaseModel):
    """Readiness check response for load balancer integration."""

    status: Literal["ready", "not_ready"] = Field(..., examples=["ready"])
    ready: bool = Field(..., examples=[True])
    message: Optional[str] = Field(default=None, examples=["yt-dlp not available"])


class ErrorDetail(BaseModel):
    """Structured error response.

    All API errors follow this format with machine-readable error codes
    and optional suggestions for resolution.
    """

    error_code: str = Field(
        ...,
        description="Machine-readable error code",
        examples=["INVALID_URL", "VIDEO_UNAVAILABLE", "RATE_LIMIT_EXCEEDED"],
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
        examples=["The provided URL is not a valid YouTube URL"],
    )
    details: Optional[str] = Field(
        None,
        description="Additional error context",
        examples=["Expected format: https://www.youtube.com/watch?v=VIDEO_ID"],
    )
    timestamp: str = Field(..., examples=["2025-12-25T10:30:00Z"])
    request_id: Optional[str] = Field(
        None,
        description="Request ID for tracing",
        examples=["req-550e8400-e29b-41d4"],
    )
    suggestion: Optional[str] = Field(
        None,
        description="Suggested action to resolve the error",
        examples=["Verify the URL format and ensure it's from a supported domain"],
    )
