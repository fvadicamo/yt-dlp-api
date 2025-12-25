"""Mock yt-dlp command execution for test mode.

This module provides a mock executor that intercepts yt-dlp commands
and returns demo data instead of making real requests to YouTube.
Used when APP_TESTING_TEST_MODE=true.
"""

import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import structlog

from app.testing.fixtures import get_demo_formats, get_demo_video

logger = structlog.get_logger(__name__)


@dataclass
class MockProcessResult:
    """Result from mock command execution."""

    returncode: int
    stdout: bytes
    stderr: bytes


class MockYtdlpExecutor:
    """Mock yt-dlp command executor for test mode.

    Intercepts yt-dlp commands and returns demo data based on the
    video ID extracted from the URL.
    """

    def __init__(self, output_dir: str = "/app/downloads"):
        """Initialize mock executor.

        Args:
            output_dir: Directory for mock download outputs.
        """
        self.output_dir = output_dir

    async def execute(
        self,
        cmd: List[str],
        timeout: Optional[float] = None,
    ) -> MockProcessResult:
        """Execute mocked yt-dlp command.

        Args:
            cmd: Command arguments (yt-dlp command)
            timeout: Ignored in mock mode

        Returns:
            MockProcessResult with simulated output.
        """
        logger.debug("mock_ytdlp_execute", cmd=cmd)

        # Parse command to determine operation
        if "--dump-json" in cmd or "-j" in cmd:
            return await self._mock_get_info(cmd)
        elif "-F" in cmd or "--list-formats" in cmd:
            return await self._mock_list_formats(cmd)
        elif self._is_download_command(cmd):
            return await self._mock_download(cmd)
        else:
            # Unknown command, return success
            return MockProcessResult(returncode=0, stdout=b"", stderr=b"")

    def _is_download_command(self, cmd: List[str]) -> bool:
        """Check if command is a download operation.

        Downloads are identified by:
        - -o (output template)
        - --print after_move:filepath (used for file path extraction)
        """
        # Check for -o flag
        if any(arg.startswith("-o") for arg in cmd):
            return True
        # Check for --print after_move:filepath pattern
        return any(
            arg == "--print" and i + 1 < len(cmd) and "filepath" in cmd[i + 1]
            for i, arg in enumerate(cmd)
        )

    async def _mock_get_info(self, cmd: List[str]) -> MockProcessResult:
        """Mock metadata extraction (--dump-json).

        Returns demo video metadata as JSON.
        """
        url = self._extract_url(cmd)
        video_id = self._extract_video_id(url)

        logger.debug("mock_get_info", video_id=video_id, url=url)

        demo_data = get_demo_video(video_id)
        stdout = json.dumps(demo_data).encode("utf-8")

        return MockProcessResult(returncode=0, stdout=stdout, stderr=b"")

    async def _mock_list_formats(self, cmd: List[str]) -> MockProcessResult:
        """Mock format listing (-F).

        Returns formatted list of available formats.
        """
        url = self._extract_url(cmd)
        video_id = self._extract_video_id(url)

        formats = get_demo_formats(video_id)

        # Build format listing output
        lines = ["[info] Available formats for DEMO_VIDEO:"]
        lines.append(
            "ID  EXT   RESOLUTION FPS |   FILESIZE   TBR PROTO | VCODEC        VBR ACODEC      ABR"
        )
        lines.append("-" * 80)

        for fmt in formats:
            resolution = fmt.get("resolution", "N/A")
            ext = fmt.get("ext", "mp4")
            format_id = fmt.get("format_id", "0")
            filesize = fmt.get("filesize", 0)
            filesize_str = f"{filesize / 1024 / 1024:.1f}MiB" if filesize else "N/A"

            lines.append(f"{format_id:3s} {ext:5s} {resolution:10s}     | {filesize_str:>10s}")

        stdout = "\n".join(lines).encode("utf-8")
        return MockProcessResult(returncode=0, stdout=stdout, stderr=b"")

    async def _mock_download(self, cmd: List[str]) -> MockProcessResult:
        """Mock download operation.

        Creates a small mock file to simulate download.
        """
        url = self._extract_url(cmd)
        video_id = self._extract_video_id(url)
        output_template = self._extract_output_template(cmd)

        logger.info(
            "mock_download",
            video_id=video_id,
            output_template=output_template,
            output_dir=self.output_dir,
        )

        # Simulate download delay
        await asyncio.sleep(0.3)

        # Determine output filename
        demo_data = get_demo_video(video_id)
        title = demo_data.get("title", "Demo Video")
        ext = "mp4"

        # Check if audio extraction is requested
        if "-x" in cmd or "--extract-audio" in cmd:
            ext = "mp3"
            for i, arg in enumerate(cmd):
                if arg == "--audio-format" and i + 1 < len(cmd):
                    ext = cmd[i + 1]
                    break

        # Generate safe filename
        safe_title = re.sub(r"[^\w\s-]", "", title)[:50]
        filename = f"{safe_title}-{video_id}.{ext}"

        # Create mock output file
        output_path = Path(self.output_dir) / filename

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create mock file with minimal content
        mock_content = f"MOCK FILE: {video_id}\nTitle: {title}\nFormat: {ext}\n"
        output_path.write_text(mock_content)

        logger.info(
            "mock_download_complete",
            output_path=str(output_path),
            file_exists=output_path.exists(),
        )

        # Return success with download message
        # The file path should be on a line that doesn't start with [
        # This matches what --print after_move:filepath outputs
        stdout = f"[download] {filename}\n[download] 100% of 1.00MiB\n{output_path}".encode("utf-8")

        return MockProcessResult(returncode=0, stdout=stdout, stderr=b"")

    def _extract_url(self, cmd: List[str]) -> str:
        """Extract URL from command arguments.

        The URL is typically the last non-option argument.
        """
        for arg in reversed(cmd):
            if arg.startswith("http"):
                return arg
        return ""

    def _extract_video_id(self, url: str) -> str:
        """Extract video ID from YouTube URL.

        Supports various YouTube URL formats:
        - https://www.youtube.com/watch?v=VIDEO_ID
        - https://youtu.be/VIDEO_ID
        - https://www.youtube.com/embed/VIDEO_ID
        """
        patterns = [
            r"(?:v=|/)([a-zA-Z0-9_-]{11})(?:&|$|/)",
            r"youtu\.be/([a-zA-Z0-9_-]{11})",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        # Return a default ID if not found
        return "DEMO_VIDEO"

    def _extract_output_template(self, cmd: List[str]) -> str:
        """Extract output template from -o argument."""
        for i, arg in enumerate(cmd):
            if arg == "-o" and i + 1 < len(cmd):
                return cmd[i + 1]
            if arg.startswith("-o"):
                return arg[2:]
        return "%(title)s-%(id)s.%(ext)s"
