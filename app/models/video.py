"""Video data models for provider abstraction."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class VideoInfo:
    """Video metadata information."""

    video_id: str
    title: str
    duration: int  # seconds
    author: str
    upload_date: str  # ISO 8601
    view_count: int
    thumbnail_url: str
    description: str


@dataclass
class VideoFormat:
    """Video format information."""

    format_id: str
    ext: str
    resolution: Optional[str] = None  # e.g., "1920x1080"
    audio_bitrate: Optional[int] = None  # kbps
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    filesize: Optional[int] = None  # bytes
    format_type: str = "video+audio"  # "video+audio", "video-only", "audio-only"


@dataclass
class Subtitle:
    """Subtitle information."""

    language: str
    format: str  # "vtt" or "srt"
    auto_generated: bool


@dataclass
class DownloadResult:
    """Result of a download operation."""

    file_path: str
    file_size: int
    duration: float  # seconds
    format_id: str
