"""E2E tests for the transcript endpoint in test mode.

The mock yt-dlp executor serves demo captions: dQw4w9WgXcQ has manual
subtitles and auto-captions, jNQXAC9IVRw only auto-captions, and only
language "en" exists.
"""


class TestTranscriptWorkflow:
    """Complete transcript retrieval through the API surface."""

    def test_transcript_json(self, e2e_client, auth_headers, demo_video_url):
        """Manual subtitles returned as JSON segments."""
        response = e2e_client.get(
            "/api/v1/transcript",
            params={"url": demo_video_url},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["video_id"] == "dQw4w9WgXcQ"
        assert data["lang"] == "en"
        assert data["source"] == "manual"
        assert data["segment_count"] == 3
        assert data["segments"][0]["text"] == "We're no strangers to love"
        assert "full commitment" in data["text"]

    def test_transcript_auto_fallback(self, e2e_client, auth_headers, short_video_url):
        """Video without manual subs falls back to auto-captions."""
        response = e2e_client.get(
            "/api/v1/transcript",
            params={"url": short_video_url},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.json()["source"] == "auto"

    def test_transcript_text_format(self, e2e_client, auth_headers, demo_video_url):
        """Plain text output is line-per-segment."""
        response = e2e_client.get(
            "/api/v1/transcript",
            params={"url": demo_video_url, "fmt": "text"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        lines = response.text.split("\n")
        assert len(lines) == 3
        assert lines[0] == "We're no strangers to love"

    def test_transcript_srt_format(self, e2e_client, auth_headers, demo_video_url):
        """SRT output uses numbered cues with comma separators."""
        response = e2e_client.get(
            "/api/v1/transcript",
            params={"url": demo_video_url, "fmt": "srt"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.text.startswith("1\n00:00:00,000 --> 00:00:02,500")

    def test_transcript_missing_language(self, e2e_client, auth_headers, demo_video_url):
        """Languages without captions return 404 TRANSCRIPT_NOT_FOUND."""
        response = e2e_client.get(
            "/api/v1/transcript",
            params={"url": demo_video_url, "lang": "it"},
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert response.json()["detail"]["error_code"] == "TRANSCRIPT_NOT_FOUND"

    def test_transcript_manual_only_missing(self, e2e_client, auth_headers, short_video_url):
        """source=manual on an auto-only video returns 404."""
        response = e2e_client.get(
            "/api/v1/transcript",
            params={"url": short_video_url, "source": "manual"},
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_transcript_requires_auth(self, e2e_client, demo_video_url):
        """Transcript endpoint rejects unauthenticated requests."""
        response = e2e_client.get("/api/v1/transcript", params={"url": demo_video_url})

        assert response.status_code == 401
