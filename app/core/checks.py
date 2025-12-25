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
from typing import Any, Callable, Dict, List, Optional, Tuple


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


async def _run_binary_check(
    name: str,
    command: List[str],
    timeout: float,
    parse_output: Callable[[bytes], Tuple[bool, Optional[str], Optional[str]]],
) -> CheckResult:
    """Run a binary availability check with common error handling.

    This helper function handles the boilerplate of running a subprocess
    and catching common exceptions (timeout, file not found, etc.).

    Args:
        name: Component name for the result (e.g., "ytdlp", "ffmpeg").
        command: Command and arguments to execute.
        timeout: Maximum time to wait in seconds.
        parse_output: Callback to parse stdout and determine success.
            Should return (success, version, error_message).

    Returns:
        CheckResult with availability status.
    """
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        if proc.returncode == 0:
            success, version, error = parse_output(stdout)
            if success:
                return CheckResult(name=name, available=True, version=version)
            return CheckResult(name=name, available=False, version=version, error=error)

        return CheckResult(
            name=name,
            available=False,
            error=f"{command[0]} returned non-zero exit code",
        )
    except asyncio.TimeoutError:
        if proc:
            proc.kill()
            await proc.wait()
        return CheckResult(
            name=name,
            available=False,
            error=f"{command[0]} check timed out",
        )
    except FileNotFoundError:
        return CheckResult(
            name=name,
            available=False,
            error=f"{command[0]} not found",
        )
    except Exception as e:
        return CheckResult(
            name=name,
            available=False,
            error=str(e),
        )


async def check_ytdlp(timeout: float = 5.0) -> CheckResult:
    """Check yt-dlp availability and version.

    Args:
        timeout: Maximum time to wait for the check in seconds.

    Returns:
        CheckResult with availability status and version if available.
    """

    def parse_version(stdout: bytes) -> Tuple[bool, Optional[str], Optional[str]]:
        version = stdout.decode().strip()
        return True, version, None

    return await _run_binary_check(
        name="ytdlp",
        command=["yt-dlp", "--version"],
        timeout=timeout,
        parse_output=parse_version,
    )


async def check_ffmpeg(timeout: float = 5.0) -> CheckResult:
    """Check ffmpeg availability and version.

    Args:
        timeout: Maximum time to wait for the check in seconds.

    Returns:
        CheckResult with availability status and version if available.
    """

    def parse_version(stdout: bytes) -> Tuple[bool, Optional[str], Optional[str]]:
        output = stdout.decode()
        match = re.search(r"ffmpeg version (\S+)", output)
        version = match.group(1) if match else "unknown"
        return True, version, None

    return await _run_binary_check(
        name="ffmpeg",
        command=["ffmpeg", "-version"],
        timeout=timeout,
        parse_output=parse_version,
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

    def parse_version(stdout: bytes) -> Tuple[bool, Optional[str], Optional[str]]:
        version = stdout.decode().strip()
        try:
            major_version = int(version.lstrip("v").split(".")[0])
        except (ValueError, IndexError):
            return False, version, f"Unable to parse Node.js version: {version}"

        if major_version >= min_version:
            return True, version, None

        return False, version, f"Node.js >= {min_version} required, found {version}"

    return await _run_binary_check(
        name="nodejs",
        command=["node", "--version"],
        timeout=timeout,
        parse_output=parse_version,
    )
