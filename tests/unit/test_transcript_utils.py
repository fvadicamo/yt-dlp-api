"""Tests for WebVTT transcript parsing and rendering utilities."""

from app.utils.transcript import TranscriptSegment, parse_vtt, segments_to_srt, segments_to_text

SIMPLE_VTT = """WEBVTT

00:00:00.000 --> 00:00:02.500
We're no strangers to love

00:00:02.500 --> 00:00:05.000
You know the rules and so do I
"""

VTT_WITH_HOURS_AND_METADATA = """WEBVTT
Kind: captions
Language: en

NOTE This block must be ignored

STYLE
::cue { color: white }

01:02:03.500 --> 01:02:05.250
Deep into the video
"""

# YouTube auto-caption style: word-level tags and rolling duplicate lines
AUTO_CAPTION_VTT = """WEBVTT

00:00:00.000 --> 00:00:01.900
<c>We're</c><00:00:00.500><c> no</c><00:00:00.800><c> strangers</c>

00:00:01.900 --> 00:00:03.500
We're no strangers
to love

00:00:03.500 --> 00:00:05.000
to love
you know the rules
"""


class TestParseVtt:
    """VTT parsing behavior."""

    def test_simple_cues(self):
        """Plain cues parse into ordered timed segments."""
        segments = parse_vtt(SIMPLE_VTT)

        assert len(segments) == 2
        assert segments[0].start == 0.0
        assert segments[0].end == 2.5
        assert segments[0].text == "We're no strangers to love"
        assert segments[1].text == "You know the rules and so do I"

    def test_hours_and_non_cue_blocks(self):
        """Header, NOTE and STYLE blocks are skipped; hour timestamps work."""
        segments = parse_vtt(VTT_WITH_HOURS_AND_METADATA)

        assert len(segments) == 1
        assert segments[0].start == 3723.5  # 1h 2m 3.5s
        assert segments[0].text == "Deep into the video"

    def test_auto_caption_tags_and_dedupe(self):
        """Inline tags are stripped and rolling duplicate lines dropped."""
        segments = parse_vtt(AUTO_CAPTION_VTT)

        texts = [s.text for s in segments]
        assert texts[0] == "We're no strangers"
        # Second cue repeats "We're no strangers" (dropped), adds "to love"
        assert texts[1] == "to love"
        # Third cue repeats "to love" (dropped), adds the new line
        assert texts[2] == "you know the rules"

    def test_empty_content(self):
        """Empty or header-only content yields no segments."""
        assert parse_vtt("") == []
        assert parse_vtt("WEBVTT\n") == []

    def test_cue_with_identifier_line(self):
        """Cues with an identifier line before the timing parse correctly."""
        vtt = "WEBVTT\n\ncue-1\n00:00:01.000 --> 00:00:02.000\nHello there\n"
        segments = parse_vtt(vtt)

        assert len(segments) == 1
        assert segments[0].text == "Hello there"


class TestRenderers:
    """Plain text and SRT rendering."""

    def test_segments_to_text(self):
        """Text output joins segments line by line."""
        segments = [
            TranscriptSegment(start=0.0, end=1.0, text="line one"),
            TranscriptSegment(start=1.0, end=2.0, text="line two"),
        ]

        assert segments_to_text(segments) == "line one\nline two"

    def test_segments_to_srt(self):
        """SRT output numbers cues and uses comma decimal separators."""
        segments = [TranscriptSegment(start=61.5, end=63.25, text="hello")]

        srt = segments_to_srt(segments)

        assert srt == "1\n00:01:01,500 --> 00:01:03,250\nhello\n"

    def test_empty_renderers(self):
        """Empty segment lists render as empty strings."""
        assert segments_to_text([]) == ""
        assert segments_to_srt([]) == ""
