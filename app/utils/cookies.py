"""Cookie file handling for yt-dlp executions.

yt-dlp rewrites the cookie jar file on every run (cookie value
rotation). The recommended deployment mounts the cookies directory
read-only, which made every real invocation crash with
"OSError: Read-only file system" (BUG-002). Executions therefore run
against a private writable copy that is discarded afterwards: refreshing
cookies is the job of the hot-reload endpoint, not of yt-dlp write-back.
"""

import contextlib
import os
import shutil
import tempfile
from typing import Iterator, List

import structlog

logger = structlog.get_logger(__name__)


@contextlib.contextmanager
def exec_cookie_copy(cmd: List[str]) -> Iterator[List[str]]:
    """Yield the command with its --cookies argument pointing to a temp copy.

    When the command has no ``--cookies`` argument, or the referenced file
    does not exist (missing cookies produce the usual yt-dlp error), the
    command is yielded unchanged.

    Args:
        cmd: yt-dlp command argument list.

    Yields:
        The command list, with the cookie path swapped for a private
        writable copy that is deleted on exit.
    """
    try:
        cookie_index = cmd.index("--cookies") + 1
    except ValueError:
        yield cmd
        return

    if cookie_index >= len(cmd):
        yield cmd
        return

    cookie_path = cmd[cookie_index]
    if not os.path.isfile(cookie_path):
        yield cmd
        return

    fd, temp_path = tempfile.mkstemp(prefix="ytdlp-cookies-", suffix=".txt")
    try:
        with os.fdopen(fd, "wb") as target, open(cookie_path, "rb") as source:
            shutil.copyfileobj(source, target)

        patched = list(cmd)
        patched[cookie_index] = temp_path
        yield patched
    finally:
        with contextlib.suppress(OSError):
            os.unlink(temp_path)
