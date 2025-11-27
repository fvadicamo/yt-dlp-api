"""Abstract base class for video providers."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from app.models.video import DownloadResult, VideoFormat


class VideoProvider(ABC):
    """Abstract base class for video platform providers."""

    @abstractmethod
    def validate_url(self, url: str) -> bool:
        """
        Validate if URL belongs to this provider.

        Args:
            url: Video URL to validate

        Returns:
            True if URL is valid for this provider, False otherwise
        """
        pass

    @abstractmethod
    async def get_info(
        self, url: str, include_formats: bool = False, include_subtitles: bool = False
    ) -> Dict:
        """
        Extract video metadata.

        Args:
            url: Video URL
            include_formats: Whether to include format list
            include_subtitles: Whether to include subtitle list

        Returns:
            Dictionary containing video information

        Raises:
            InvalidURLError: If URL is invalid
            VideoUnavailableError: If video is not accessible
            AuthenticationError: If authentication fails
        """
        pass

    @abstractmethod
    async def list_formats(self, url: str) -> List[VideoFormat]:
        """
        List all available formats for a video.

        Args:
            url: Video URL

        Returns:
            List of available formats

        Raises:
            InvalidURLError: If URL is invalid
            VideoUnavailableError: If video is not accessible
        """
        pass

    @abstractmethod
    async def download(
        self,
        url: str,
        format_id: Optional[str] = None,
        output_template: Optional[str] = None,
        extract_audio: bool = False,
        audio_format: Optional[str] = None,
        include_subtitles: bool = False,
        subtitle_lang: Optional[str] = None,
    ) -> DownloadResult:
        """
        Download video/audio.

        Args:
            url: Video URL
            format_id: Specific format to download
            output_template: Custom output filename template
            extract_audio: Whether to extract audio only
            audio_format: Audio format (mp3, m4a, wav, opus)
            include_subtitles: Whether to download subtitles
            subtitle_lang: Subtitle language code

        Returns:
            Download result with file path and metadata

        Raises:
            InvalidURLError: If URL is invalid
            VideoUnavailableError: If video is not accessible
            FormatNotFoundError: If requested format is not available
            DownloadError: If download fails
            TranscodingError: If audio conversion fails
        """
        pass

    @abstractmethod
    def get_cookie_path(self) -> Optional[str]:
        """
        Get provider-specific cookie file path.

        Returns:
            Path to cookie file, or None if not required
        """
        pass
