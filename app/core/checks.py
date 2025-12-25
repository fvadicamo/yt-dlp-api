"""Shared component check utilities.

This module provides reusable async functions for checking external
dependencies like yt-dlp, ffmpeg, and Node.js. Used by both the
startup validator and health check endpoints.

Implements requirements:
- Req 10: JavaScript Challenge Resolution (Node.js >= 20)
- Req 11: Health monitoring with component verification
"""

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class CheckResult:
    """Result of a component availability check.

    Attributes:
        name: Component name (e.g., "ytdlp", "ffmpeg", "nodejs")
        available: Whether the component is available and functional
        version: Version string if available
        error: Error message if check failed
        details: Additional details about the check result
    """

    name: str
    available: bool
    version: Optional[str] = None
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


async def check_ytdlp(timeout: float = 5.0) -> CheckResult:
    """Check yt-dlp availability and version.

    Args:
        timeout: Maximum time to wait for the check in seconds.

    Returns:
        CheckResult with availability status and version if available.
    """
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        if proc.returncode == 0:
            version = stdout.decode().strip()
            return CheckResult(name="ytdlp", available=True, version=version)

        return CheckResult(
            name="ytdlp",
            available=False,
            error="yt-dlp returned non-zero exit code",
        )
    except asyncio.TimeoutError:
        if proc:
            proc.kill()
            await proc.wait()
        return CheckResult(
            name="ytdlp",
            available=False,
            error="yt-dlp check timed out",
        )
    except FileNotFoundError:
        return CheckResult(
            name="ytdlp",
            available=False,
            error="yt-dlp not found",
        )
    except Exception as e:
        return CheckResult(
            name="ytdlp",
            available=False,
            error=str(e),
        )


async def check_ffmpeg(timeout: float = 5.0) -> CheckResult:
    """Check ffmpeg availability and version.

    Args:
        timeout: Maximum time to wait for the check in seconds.

    Returns:
        CheckResult with availability status and version if available.
    """
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        if proc.returncode == 0:
            # Extract version using regex for robustness
            output = stdout.decode()
            match = re.search(r"ffmpeg version (\S+)", output)
            version = match.group(1) if match else "unknown"
            return CheckResult(name="ffmpeg", available=True, version=version)

        return CheckResult(
            name="ffmpeg",
            available=False,
            error="ffmpeg returned non-zero exit code",
        )
    except asyncio.TimeoutError:
        if proc:
            proc.kill()
            await proc.wait()
        return CheckResult(
            name="ffmpeg",
            available=False,
            error="ffmpeg check timed out",
        )
    except FileNotFoundError:
        return CheckResult(
            name="ffmpeg",
            available=False,
            error="ffmpeg not found",
        )
    except Exception as e:
        return CheckResult(
            name="ffmpeg",
            available=False,
            error=str(e),
        )


async def check_nodejs(min_version: int = 20, timeout: float = 5.0) -> CheckResult:
    """Check Node.js availability and version.

    Args:
        min_version: Minimum required major version (default: 20).
        timeout: Maximum time to wait for the check in seconds.

    Returns:
        CheckResult with availability status. available=False if
        Node.js is not installed or version is below min_version.
    """
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            "node",
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        if proc.returncode == 0:
            version = stdout.decode().strip()
            # Parse version (format: v20.10.0)
            try:
                major_version = int(version.lstrip("v").split(".")[0])
            except (ValueError, IndexError):
                return CheckResult(
                    name="nodejs",
                    available=False,
                    version=version,
                    error=f"Unable to parse Node.js version: {version}",
                )

            if major_version >= min_version:
                return CheckResult(name="nodejs", available=True, version=version)

            return CheckResult(
                name="nodejs",
                available=False,
                version=version,
                error=f"Node.js >= {min_version} required, found {version}",
            )

        return CheckResult(
            name="nodejs",
            available=False,
            error="node returned non-zero exit code",
        )
    except asyncio.TimeoutError:
        if proc:
            proc.kill()
            await proc.wait()
        return CheckResult(
            name="nodejs",
            available=False,
            error="node check timed out",
        )
    except FileNotFoundError:
        return CheckResult(
            name="nodejs",
            available=False,
            error="node not found",
        )
    except Exception as e:
        return CheckResult(
            name="nodejs",
            available=False,
            error=str(e),
        )
