"""Tests for the writable cookie copy used by yt-dlp executions (BUG-002)."""

import contextlib
import os
import stat

from app.utils.cookies import exec_cookie_copy

COOKIE_CONTENT = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tX\tY\n"


class TestExecCookieCopy:
    """Behavior of the --cookies rewrite context manager."""

    def test_rewrites_cookie_path_with_writable_copy(self, tmp_path):
        """The command gets a temp copy with identical content; copy is writable."""
        cookie_file = tmp_path / "youtube.txt"
        cookie_file.write_text(COOKIE_CONTENT)
        # Simulate a read-only mount
        cookie_file.chmod(stat.S_IRUSR)

        cmd = ["yt-dlp", "--cookies", str(cookie_file), "--simulate", "url"]

        with exec_cookie_copy(cmd) as exec_cmd:
            copy_path = exec_cmd[2]
            assert copy_path != str(cookie_file)
            with open(copy_path) as f:
                assert f.read() == COOKIE_CONTENT
            assert os.access(copy_path, os.W_OK)
            # Other arguments untouched
            assert exec_cmd[0] == "yt-dlp"
            assert exec_cmd[3:] == ["--simulate", "url"]

        assert not os.path.exists(copy_path)

    def test_original_file_untouched_by_copy_writes(self, tmp_path):
        """Writes to the copy (yt-dlp jar rewrite) never reach the original."""
        cookie_file = tmp_path / "youtube.txt"
        cookie_file.write_text(COOKIE_CONTENT)

        cmd = ["yt-dlp", "--cookies", str(cookie_file), "url"]

        with exec_cookie_copy(cmd) as exec_cmd, open(exec_cmd[2], "a") as f:
            f.write("rotated-cookie-value\n")

        assert cookie_file.read_text() == COOKIE_CONTENT

    def test_no_cookies_argument_passthrough(self):
        """Commands without --cookies are yielded unchanged."""
        cmd = ["yt-dlp", "--dump-json", "url"]

        with exec_cookie_copy(cmd) as exec_cmd:
            assert exec_cmd is cmd

    def test_missing_cookie_file_passthrough(self, tmp_path):
        """A missing cookie file keeps the original path (usual yt-dlp error)."""
        missing = str(tmp_path / "nope.txt")
        cmd = ["yt-dlp", "--cookies", missing, "url"]

        with exec_cookie_copy(cmd) as exec_cmd:
            assert exec_cmd is cmd

    def test_trailing_cookies_flag_passthrough(self):
        """A dangling --cookies at the end of the command is left alone."""
        cmd = ["yt-dlp", "--cookies"]

        with exec_cookie_copy(cmd) as exec_cmd:
            assert exec_cmd is cmd

    def test_copy_removed_even_on_exception(self, tmp_path):
        """The temp copy is deleted when the block raises."""
        cookie_file = tmp_path / "youtube.txt"
        cookie_file.write_text(COOKIE_CONTENT)
        cmd = ["yt-dlp", "--cookies", str(cookie_file), "url"]

        copy_path = None
        with contextlib.suppress(RuntimeError), exec_cookie_copy(cmd) as exec_cmd:
            copy_path = exec_cmd[2]
            raise RuntimeError("boom")

        assert copy_path is not None
        assert not os.path.exists(copy_path)
