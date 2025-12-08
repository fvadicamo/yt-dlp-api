"""YouTube provider implementation."""

import asyncio
import json
import re
import subprocess  # nosec B404 - subprocess used for returning CompletedProcess
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from app.models.video import DownloadResult, VideoFormat
from app.providers.base import VideoProvider
from app.providers.exceptions import DownloadError, InvalidURLError, VideoUnavailableError

logger = structlog.get_logger(__name__)


class YouTubeProvider(VideoProvider):
    """YouTube video provider implementation."""

    # URL patterns for YouTube videos
    URL_PATTERNS = [
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+",
        r"(?:https?://)?(?:www\.)?youtube\.com/shorts/[\w-]+",
        r"(?:https?://)?(?:www\.)?youtube\.com/embed/[\w-]+",
        r"(?:https?://)?youtu\.be/[\w-]+",
        r"(?:https?://)?m\.youtube\.com/watch\?v=[\w-]+",
    ]

    # Pattern to extract video ID
    VIDEO_ID_PATTERN = r"(?:v=|shorts/|embed/|youtu\.be/)([\w-]+)"

    def __init__(self, config: dict, cookie_service: Optional[Any] = None):
        """
        Initialize YouTube provider.

        Args:
            config: Provider configuration dictionary
            cookie_service: Optional CookieService instance for validation
        """
        self.config = config
        self.cookie_path: str = config.get("cookie_path", "/app/cookies/youtube.txt")
        self.retry_attempts: int = config.get("retry_attempts", 3)
        self.retry_backoff: list = config.get("retry_backoff", [2, 4, 8])
        self.cookie_service = cookie_service

        logger.info(
            "YouTube provider initialized",
            cookie_path=self.cookie_path,
            retry_attempts=self.retry_attempts,
        )

    def validate_url(self, url: str) -> bool:
        """
        Validate if URL is a valid YouTube URL.

        Args:
            url: URL to validate

        Returns:
            True if URL is valid YouTube URL, False otherwise
        """
        if not url:
            return False

        # Check against all URL patterns
        for pattern in self.URL_PATTERNS:
            if re.match(pattern, url, re.IGNORECASE):
                logger.debug("URL validated", url=url, pattern=pattern)
                return True

        return False

    def extract_video_id(self, url: str) -> Optional[str]:
        """
        Extract video ID from YouTube URL.

        Args:
            url: YouTube URL

        Returns:
            Video ID if found, None otherwise
        """
        match = re.search(self.VIDEO_ID_PATTERN, url)
        if match:
            video_id = match.group(1)
            logger.debug("Video ID extracted", url=url, video_id=video_id)
            return video_id

        logger.warning("Could not extract video ID", url=url)
        return None

    async def get_info(  # noqa: C901
        self, url: str, include_formats: bool = False, include_subtitles: bool = False
    ) -> Dict:
        """
        Extract video metadata.

        Args:
            url: YouTube video URL
            include_formats: Whether to include format list
            include_subtitles: Whether to include subtitle list

        Returns:
            Dictionary containing video information

        Raises:
            InvalidURLError: If URL is invalid
            VideoUnavailableError: If video is not accessible
        """
        if not self.validate_url(url):
            raise InvalidURLError(f"Invalid YouTube URL: {url}")

        video_id = self.extract_video_id(url)
        if not video_id:
            raise InvalidURLError(f"Could not extract video ID from URL: {url}")

        # Validate cookie before execution
        if self.cookie_service:
            await self.cookie_service.validate_cookie("youtube")

        logger.info(
            "Getting video info",
            url=url,
            video_id=video_id,
            include_formats=include_formats,
            include_subtitles=include_subtitles,
        )

        # Build yt-dlp command
        cmd = [
            "yt-dlp",
            "--dump-json",
            "--no-download",
            "--cookies",
            self.cookie_path,
            "--extractor-args",
            "youtube:player_client=web",
        ]

        if not include_formats:
            cmd.append("--skip-download")

        cmd.append(url)

        try:
            # Execute with retry logic and 10-second timeout per attempt
            result = await self._execute_with_retry(cmd, timeout=10.0)
            stdout = result.stdout

            # Parse JSON output
            info = json.loads(stdout.decode())

            # Transform to our format
            video_info: Dict = {
                "video_id": info.get("id", video_id),
                "title": info.get("title", ""),
                "duration": info.get("duration", 0),
                "author": info.get("uploader", ""),
                "upload_date": info.get("upload_date", ""),
                "view_count": info.get("view_count", 0),
                "thumbnail_url": info.get("thumbnail", ""),
                "description": info.get("description", ""),
            }

            # Add formats if requested
            if include_formats and "formats" in info:
                video_info["formats"] = self._parse_formats(info["formats"])

            # Add subtitles if requested
            if include_subtitles and "subtitles" in info:
                video_info["subtitles"] = self._parse_subtitles(info.get("subtitles", {}))

            logger.info("Video info extracted successfully", video_id=video_id)
            return video_info

        except DownloadError as e:
            # Check if this is a video availability issue
            error_str = str(e)
            if "Video unavailable" in error_str or "Private video" in error_str:
                raise VideoUnavailableError(f"Video is not accessible: {error_str}")
            raise
        except json.JSONDecodeError as e:
            logger.error("Failed to parse yt-dlp output", error=str(e))
            raise DownloadError(f"Failed to parse video info: {str(e)}")

    def _parse_formats(self, formats: List[Dict]) -> List[Dict]:
        """
        Parse format information from yt-dlp output.

        Args:
            formats: List of format dictionaries from yt-dlp

        Returns:
            List of parsed format dictionaries
        """
        parsed_formats = []

        for fmt in formats:
            format_dict = {
                "format_id": fmt.get("format_id", ""),
                "ext": fmt.get("ext", ""),
                "resolution": fmt.get("resolution"),
                "audio_bitrate": fmt.get("abr"),
                "video_codec": fmt.get("vcodec"),
                "audio_codec": fmt.get("acodec"),
                "filesize": fmt.get("filesize"),
                "format_type": self._categorize_format(fmt),
            }
            parsed_formats.append(format_dict)

        return parsed_formats

    def _categorize_format(self, fmt: Dict) -> str:
        """
        Categorize format as video+audio, video-only, or audio-only.

        Args:
            fmt: Format dictionary from yt-dlp

        Returns:
            Format type string
        """
        has_video = fmt.get("vcodec") not in [None, "none"]
        has_audio = fmt.get("acodec") not in [None, "none"]

        if has_video and has_audio:
            return "video+audio"
        elif has_video:
            return "video-only"
        elif has_audio:
            return "audio-only"
        else:
            return "unknown"

    def _parse_subtitles(self, subtitles: Dict) -> List[Dict]:
        """
        Parse subtitle information from yt-dlp output.

        Args:
            subtitles: Subtitle dictionary from yt-dlp

        Returns:
            List of parsed subtitle dictionaries
        """
        parsed_subtitles = []

        for lang, sub_list in subtitles.items():
            for sub in sub_list:
                subtitle_dict = {
                    "language": lang,
                    "format": sub.get("ext", ""),
                    "auto_generated": sub.get("name", "").startswith("auto-generated"),
                }
                parsed_subtitles.append(subtitle_dict)

        return parsed_subtitles

    async def list_formats(self, url: str) -> List[VideoFormat]:
        """
        List all available formats.

        Args:
            url: YouTube video URL

        Returns:
            List of available formats sorted by quality

        Raises:
            InvalidURLError: If URL is invalid
            VideoUnavailableError: If video is not accessible
        """
        if not self.validate_url(url):
            raise InvalidURLError(f"Invalid YouTube URL: {url}")

        video_id = self.extract_video_id(url)
        if not video_id:
            raise InvalidURLError(f"Could not extract video ID from URL: {url}")

        logger.info("Listing formats", url=url, video_id=video_id)

        # Get video info with formats
        info = await self.get_info(url, include_formats=True, include_subtitles=False)

        # Extract and convert formats
        formats_data = info.get("formats", [])
        formats = []

        for fmt_dict in formats_data:
            video_format = VideoFormat(
                format_id=fmt_dict["format_id"],
                ext=fmt_dict["ext"],
                resolution=fmt_dict.get("resolution"),
                audio_bitrate=fmt_dict.get("audio_bitrate"),
                video_codec=fmt_dict.get("video_codec"),
                audio_codec=fmt_dict.get("audio_codec"),
                filesize=fmt_dict.get("filesize"),
                format_type=fmt_dict["format_type"],
            )
            formats.append(video_format)

        # Sort by quality (highest to lowest)
        # Priority: resolution > filesize > format_id
        formats.sort(
            key=lambda f: (self._get_resolution_value(f.resolution), f.filesize or 0, f.format_id),
            reverse=True,
        )

        logger.info("Formats listed", video_id=video_id, count=len(formats))
        return formats

    def _get_resolution_value(self, resolution: Optional[str]) -> int:
        """
        Extract numeric value from resolution string for sorting.

        Args:
            resolution: Resolution string (e.g., "1920x1080", "audio only")

        Returns:
            Numeric value for sorting (height in pixels)
        """
        if not resolution:
            return 0

        # Handle "audio only" case
        if "audio" in resolution.lower():
            return 0

        # Extract height from resolution (e.g., "1920x1080" -> 1080)
        match = re.search(r"(\d+)x(\d+)", resolution)
        if match:
            return int(match.group(2))  # Return height

        # Try to extract any number
        match = re.search(r"(\d+)", resolution)
        if match:
            return int(match.group(1))

        return 0

    async def download(  # noqa: C901
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
            url: YouTube video URL
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
            DownloadError: If download fails
        """
        if not self.validate_url(url):
            raise InvalidURLError(f"Invalid YouTube URL: {url}")

        video_id = self.extract_video_id(url)
        if not video_id:
            raise InvalidURLError(f"Could not extract video ID from URL: {url}")

        # Validate cookie before execution
        if self.cookie_service:
            await self.cookie_service.validate_cookie("youtube")

        logger.info(
            "Starting download",
            url=url,
            video_id=video_id,
            format_id=format_id,
            extract_audio=extract_audio,
            audio_format=audio_format,
        )

        # Build yt-dlp command
        cmd = [
            "yt-dlp",
            "--cookies",
            self.cookie_path,
            "--extractor-args",
            "youtube:player_client=web",
            "--print",
            "after_move:filepath",  # Print final file path
        ]

        # Format selection
        if format_id:
            cmd.extend(["-f", format_id])

        # Audio extraction
        if extract_audio:
            cmd.extend(["-x", "--audio-format", audio_format or "mp3"])
            if audio_format in ["mp3", "m4a"]:
                cmd.extend(["--audio-quality", "0"])  # Best quality

        # Output template
        if output_template:
            cmd.extend(["-o", output_template])

        # Subtitles
        if include_subtitles:
            cmd.append("--write-subs")
            if subtitle_lang:
                cmd.extend(["--sub-langs", subtitle_lang])

        cmd.append(url)

        # Log command with redaction (Req 17A)
        logger.debug("Executing yt-dlp", command=self._redact_command(cmd))

        start_time = asyncio.get_event_loop().time()

        # Execute command with retry logic (no timeout for downloads)
        # _execute_with_retry handles FileNotFoundError and raises DownloadError
        result = await self._execute_with_retry(cmd)
        stdout = result.stdout
        stderr = result.stderr

        # Log execution results (Req 17A)
        logger.debug(
            "yt-dlp execution completed",
            command=self._redact_command(cmd),
            exit_code=result.returncode,
            stdout_lines=len(stdout.decode().split("\n")) if stdout else 0,
            stderr_preview=stderr.decode()[:500] if stderr else None,
        )

        # Extract file path from output
        file_path = self._extract_file_path(stdout.decode())
        if not file_path:
            raise DownloadError("Could not determine output file path")

        # Get file size
        file_size = Path(file_path).stat().st_size
        duration = asyncio.get_event_loop().time() - start_time

        logger.info(
            "Download completed",
            video_id=video_id,
            file_path=file_path,
            file_size=file_size,
            duration=duration,
        )

        return DownloadResult(
            file_path=file_path,
            file_size=file_size,
            duration=duration,
            format_id=format_id or "best",
        )

    def _redact_command(self, cmd: List[str]) -> List[str]:
        """
        Redact sensitive information from command.

        Args:
            cmd: Command list

        Returns:
            Redacted command list
        """
        redacted = []
        skip_next = False

        for arg in cmd:
            if skip_next:
                redacted.append("[REDACTED]")
                skip_next = False
            elif arg in ["--cookies", "--password", "--username"]:
                redacted.append(arg)
                skip_next = True
            else:
                redacted.append(arg)

        return redacted

    def _extract_file_path(self, output: str) -> Optional[str]:
        """
        Extract file path from yt-dlp output.

        Args:
            output: yt-dlp stdout

        Returns:
            File path if found, None otherwise
        """
        lines = output.strip().split("\n")

        # Look for the filepath line (printed by --print after_move:filepath)
        for line in reversed(lines):
            line = line.strip()
            if line and not line.startswith("["):
                # This should be the file path
                return line

        return None

    def _is_retriable_error(self, error_msg: str) -> bool:
        """
        Determine if error should trigger retry per Requirement 18.

        Args:
            error_msg: Error message from yt-dlp stderr

        Returns:
            True if error is retriable, False otherwise
        """
        retriable_patterns = [
            "HTTP Error 5",  # Server errors (5xx)
            "Connection reset",  # Network issues
            "Timeout",  # Request timeout
            "Too Many Requests",  # Rate limiting (429)
            "HTTP Error 429",  # Rate limiting explicit
            "Unable to connect",  # Connection failed
        ]
        return any(pattern in error_msg for pattern in retriable_patterns)

    async def _execute_with_retry(  # noqa: C901
        self,
        cmd: List[str],
        timeout: Optional[float] = None,
    ) -> subprocess.CompletedProcess:
        """
        Execute command with retry logic per Requirement 18.

        Implements exponential backoff with configurable retry attempts.
        Distinguishes between retriable errors (network, 5xx) and
        non-retriable errors (private video, invalid URL).

        Args:
            cmd: Command to execute as list of strings
            timeout: Optional timeout in seconds for each attempt

        Returns:
            CompletedProcess with stdout and stderr

        Raises:
            DownloadError: If all retry attempts fail or non-retriable error occurs
        """
        last_error: Optional[str] = None

        for attempt in range(self.retry_attempts):
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                if timeout:
                    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                else:
                    stdout, stderr = await process.communicate()

                if process.returncode == 0:
                    return subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)

                # Non-zero return code - check if retriable
                error_msg = stderr.decode() if stderr else "Unknown error"

                if not self._is_retriable_error(error_msg):
                    # Non-retriable error - fail immediately
                    raise DownloadError(error_msg)

                last_error = error_msg

                # Retry with backoff if not last attempt
                if attempt < self.retry_attempts - 1:
                    wait_time = self.retry_backoff[attempt]
                    logger.warning(
                        "Retrying after retriable error",
                        attempt=attempt + 1,
                        max_attempts=self.retry_attempts,
                        wait_seconds=wait_time,
                        error=error_msg[:200],
                    )
                    await asyncio.sleep(wait_time)

            except asyncio.TimeoutError:
                last_error = f"Timeout after {timeout}s"
                logger.warning(
                    "Timeout during command execution",
                    attempt=attempt + 1,
                    max_attempts=self.retry_attempts,
                    timeout=timeout,
                )
                # Timeout is retriable - continue to next attempt
                if attempt < self.retry_attempts - 1:
                    wait_time = self.retry_backoff[attempt]
                    await asyncio.sleep(wait_time)

            except DownloadError:
                # Re-raise non-retriable errors immediately
                raise

            except FileNotFoundError:
                # yt-dlp not installed - fail immediately, don't retry
                logger.error("yt-dlp not found, ensure it is installed and in PATH")
                raise DownloadError("yt-dlp is not installed or not in PATH")

            except Exception as e:
                last_error = str(e)
                if attempt == self.retry_attempts - 1:
                    raise DownloadError(f"Unexpected error: {last_error}")

        raise DownloadError(f"Failed after {self.retry_attempts} attempts: {last_error}")

    def get_cookie_path(self) -> Optional[str]:
        """
        Get YouTube cookie file path.

        Returns:
            Path to cookie file
        """
        return self.cookie_path
