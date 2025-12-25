"""Demo video fixtures for test mode.

These fixtures provide realistic YouTube metadata for testing without
making actual requests to YouTube. Used when APP_TESTING_TEST_MODE=true.
"""

from typing import Any, Dict, List

# Demo video: Rick Astley - Never Gonna Give You Up
RICK_ASTLEY_VIDEO: Dict[str, Any] = {
    "id": "dQw4w9WgXcQ",
    "title": "Rick Astley - Never Gonna Give You Up (Official Music Video)",
    "duration": 212,
    "duration_string": "3:32",
    "uploader": "Rick Astley",
    "uploader_id": "@RickAstleyYT",
    "channel": "Rick Astley",
    "channel_id": "UCuAXFkgsw1L7xaCfnd5JJOw",
    "upload_date": "20091025",
    "view_count": 1500000000,
    "like_count": 15000000,
    "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
    "description": (
        "The official music video for Never Gonna Give You Up by Rick Astley.\n\n"
        "The song was a worldwide number-one hit."
    ),
    "webpage_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "extractor": "youtube",
    "extractor_key": "Youtube",
    "formats": [
        {
            "format_id": "18",
            "format_note": "360p",
            "ext": "mp4",
            "resolution": "640x360",
            "filesize": 15000000,
            "vcodec": "avc1.42001E",
            "acodec": "mp4a.40.2",
            "abr": 96,
            "vbr": 500,
        },
        {
            "format_id": "22",
            "format_note": "720p",
            "ext": "mp4",
            "resolution": "1280x720",
            "filesize": 45000000,
            "vcodec": "avc1.64001F",
            "acodec": "mp4a.40.2",
            "abr": 192,
            "vbr": 2500,
        },
        {
            "format_id": "137",
            "format_note": "1080p",
            "ext": "mp4",
            "resolution": "1920x1080",
            "filesize": 80000000,
            "vcodec": "avc1.640028",
            "acodec": None,
            "vbr": 4500,
        },
        {
            "format_id": "140",
            "format_note": "m4a audio only",
            "ext": "m4a",
            "resolution": "audio only",
            "filesize": 3400000,
            "vcodec": None,
            "acodec": "mp4a.40.2",
            "abr": 128,
        },
    ],
    "subtitles": {
        "en": [
            {"ext": "vtt", "url": "https://example.com/subtitles/en.vtt"},
        ],
    },
    "automatic_captions": {},
    "categories": ["Music"],
    "tags": ["Rick Astley", "Never Gonna Give You Up", "Music Video"],
}

# Demo video: Me at the zoo (first YouTube video, very short)
ME_AT_ZOO_VIDEO: Dict[str, Any] = {
    "id": "jNQXAC9IVRw",
    "title": "Me at the zoo",
    "duration": 19,
    "duration_string": "0:19",
    "uploader": "jawed",
    "uploader_id": "@jaboris",
    "channel": "jawed",
    "channel_id": "UC4QobU6STFB0P71PMvOGN5A",
    "upload_date": "20050423",
    "view_count": 300000000,
    "like_count": 12000000,
    "thumbnail": "https://i.ytimg.com/vi/jNQXAC9IVRw/maxresdefault.jpg",
    "description": "The first video on YouTube. Maybe it's time to go back to the zoo?",
    "webpage_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
    "extractor": "youtube",
    "extractor_key": "Youtube",
    "formats": [
        {
            "format_id": "18",
            "format_note": "360p",
            "ext": "mp4",
            "resolution": "640x360",
            "filesize": 500000,
            "vcodec": "avc1.42001E",
            "acodec": "mp4a.40.2",
            "abr": 96,
            "vbr": 500,
        },
        {
            "format_id": "140",
            "format_note": "m4a audio only",
            "ext": "m4a",
            "resolution": "audio only",
            "filesize": 150000,
            "vcodec": None,
            "acodec": "mp4a.40.2",
            "abr": 128,
        },
    ],
    "subtitles": {},
    "automatic_captions": {},
    "categories": ["People & Blogs"],
    "tags": ["zoo", "elephant"],
}

# Generic demo video for unknown URLs in test mode
GENERIC_DEMO_VIDEO: Dict[str, Any] = {
    "id": "DEMO_VIDEO",
    "title": "Demo Video for Testing",
    "duration": 60,
    "duration_string": "1:00",
    "uploader": "Test Channel",
    "uploader_id": "@TestChannel",
    "channel": "Test Channel",
    "channel_id": "UCTestChannel123",
    "upload_date": "20240101",
    "view_count": 1000,
    "like_count": 100,
    "thumbnail": "https://example.com/thumbnail.jpg",
    "description": "This is a demo video for testing purposes.",
    "webpage_url": "https://www.youtube.com/watch?v=DEMO_VIDEO",
    "extractor": "youtube",
    "extractor_key": "Youtube",
    "formats": [
        {
            "format_id": "best",
            "format_note": "720p",
            "ext": "mp4",
            "resolution": "1280x720",
            "filesize": 10000000,
            "vcodec": "avc1.64001F",
            "acodec": "mp4a.40.2",
            "abr": 128,
            "vbr": 1500,
        },
        {
            "format_id": "140",
            "format_note": "m4a audio only",
            "ext": "m4a",
            "resolution": "audio only",
            "filesize": 1000000,
            "vcodec": None,
            "acodec": "mp4a.40.2",
            "abr": 128,
        },
    ],
    "subtitles": {},
    "automatic_captions": {},
    "categories": ["Entertainment"],
    "tags": ["demo", "test"],
}

# Map of video IDs to fixtures
DEMO_VIDEOS: Dict[str, Dict[str, Any]] = {
    "dQw4w9WgXcQ": RICK_ASTLEY_VIDEO,
    "jNQXAC9IVRw": ME_AT_ZOO_VIDEO,
    "DEMO_VIDEO": GENERIC_DEMO_VIDEO,
}


def get_demo_video(video_id: str) -> Dict[str, Any]:
    """Get demo fixture for a video ID.

    Args:
        video_id: YouTube video ID to look up

    Returns:
        Demo video metadata dict. Returns generic demo if ID not found.
    """
    return DEMO_VIDEOS.get(video_id, GENERIC_DEMO_VIDEO)


def get_demo_formats(video_id: str) -> List[Dict[str, Any]]:
    """Get format list for a demo video.

    Args:
        video_id: YouTube video ID to look up

    Returns:
        List of format dicts for the video.
    """
    video = get_demo_video(video_id)
    formats: List[Dict[str, Any]] = video.get("formats", [])
    return formats
