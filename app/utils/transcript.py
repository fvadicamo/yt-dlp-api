"""WebVTT transcript parsing and rendering utilities.

Parses subtitle files fetched by yt-dlp (manual subtitles or YouTube
auto-captions) into timed segments, and renders them as plain text or
SRT. Auto-captions use rolling cues where consecutive blocks repeat the
previous line, so parsing deduplicates repeated lines.
"""

import re
from dataclasses import dataclass
from typing import List

# Cue timing line: "00:00:01.000 --> 00:00:04.000" (hours optional)
_TIMING_RE = re.compile(
    r"(?P<start>(?:\d{1,2}:)?\d{2}:\d{2}\.\d{3})\s*-->\s*(?P<end>(?:\d{1,2}:)?\d{2}:\d{2}\.\d{3})"
)

# Inline markup: word-level timestamps "<00:00:01.319>" and tags "<c>...</c>"
_INLINE_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class TranscriptSegment:
    """A single timed transcript segment."""

    start: float  # seconds
    end: float  # seconds
    text: str


def _timestamp_to_seconds(value: str) -> float:
    """Convert a VTT timestamp (HH:MM:SS.mmm or MM:SS.mmm) to seconds."""
    parts = value.split(":")
    seconds = float(parts[-1])
    minutes = int(parts[-2])
    hours = int(parts[-3]) if len(parts) == 3 else 0
    return hours * 3600 + minutes * 60 + seconds


def _seconds_to_srt_timestamp(value: float) -> str:
    """Convert seconds to an SRT timestamp (HH:MM:SS,mmm)."""
    millis = round(value * 1000)
    hours, remainder = divmod(millis, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def parse_vtt(content: str) -> List[TranscriptSegment]:
    """Parse WebVTT content into deduplicated transcript segments.

    Args:
        content: Raw VTT file content.

    Returns:
        Ordered list of segments with start/end in seconds. Lines already
        emitted by the previous cue (auto-caption rolling window) are
        dropped; segments left without text are skipped.
    """
    segments: List[TranscriptSegment] = []
    previous_lines: List[str] = []

    for block in re.split(r"\n\s*\n", content):
        lines = [line.strip() for line in block.strip().split("\n") if line.strip()]
        if not lines:
            continue

        # Locate the timing line; blocks without one (WEBVTT header,
        # NOTE/STYLE/REGION, metadata) are skipped
        timing_match = None
        timing_index = -1
        for i, line in enumerate(lines):
            timing_match = _TIMING_RE.search(line)
            if timing_match:
                timing_index = i
                break
        if not timing_match:
            continue

        text_lines = []
        for raw_line in lines[timing_index + 1 :]:
            clean = _INLINE_TAG_RE.sub("", raw_line).strip()
            if clean and clean not in previous_lines:
                text_lines.append(clean)

        # Remember the full cue text (cleaned) for rolling-window dedupe
        previous_lines = [
            _INLINE_TAG_RE.sub("", raw_line).strip() for raw_line in lines[timing_index + 1 :]
        ]

        if not text_lines:
            continue

        segments.append(
            TranscriptSegment(
                start=_timestamp_to_seconds(timing_match.group("start")),
                end=_timestamp_to_seconds(timing_match.group("end")),
                text=" ".join(text_lines),
            )
        )

    return segments


def segments_to_text(segments: List[TranscriptSegment]) -> str:
    """Render segments as plain text, one segment per line."""
    return "\n".join(segment.text for segment in segments)


def segments_to_srt(segments: List[TranscriptSegment]) -> str:
    """Render segments in SubRip (SRT) format."""
    blocks = []
    for index, segment in enumerate(segments, start=1):
        start = _seconds_to_srt_timestamp(segment.start)
        end = _seconds_to_srt_timestamp(segment.end)
        blocks.append(f"{index}\n{start} --> {end}\n{segment.text}")
    return "\n\n".join(blocks) + ("\n" if blocks else "")
