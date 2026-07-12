"""Transcript API endpoint.

Exposes video transcripts (manual subtitles or auto-captions) as timed
segments, plain text, SRT or raw VTT, without downloading any media.
"""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse

from app.api.schemas import TranscriptResponse, TranscriptSegmentResponse
from app.core.validation import URLValidator
from app.middleware.auth import require_api_key
from app.providers.exceptions import (
    InvalidURLError,
    ProviderError,
    TranscriptNotFoundError,
    VideoUnavailableError,
)
from app.providers.manager import ProviderManager
from app.utils.transcript import segments_to_srt, segments_to_text

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["video"])

# URL validator instance
url_validator = URLValidator()

# Media types for non-JSON output formats
_MEDIA_TYPES = {
    "text": "text/plain; charset=utf-8",
    "srt": "application/x-subrip",
    "vtt": "text/vtt; charset=utf-8",
}


# Dependency placeholder for provider manager
async def get_provider_manager() -> ProviderManager:
    """Get provider manager instance."""
    raise NotImplementedError("Provider manager dependency not configured")


def _render_transcript(fmt: str, transcript: dict) -> Any:
    """Render a provider transcript payload in the requested format."""
    segments = transcript["segments"]

    if fmt == "text":
        return PlainTextResponse(segments_to_text(segments), media_type=_MEDIA_TYPES["text"])
    if fmt == "srt":
        return PlainTextResponse(segments_to_srt(segments), media_type=_MEDIA_TYPES["srt"])
    if fmt == "vtt":
        return PlainTextResponse(transcript["raw_vtt"], media_type=_MEDIA_TYPES["vtt"])

    return TranscriptResponse(
        video_id=transcript["video_id"],
        lang=transcript["lang"],
        source=transcript["source"],
        segment_count=len(segments),
        segments=[
            TranscriptSegmentResponse(start=s.start, end=s.end, text=s.text) for s in segments
        ],
        text=segments_to_text(segments),
    )


@router.get(
    "/transcript",
    response_model=TranscriptResponse,
    dependencies=[Depends(require_api_key)],
    responses={
        200: {
            "description": "Transcript in the requested format",
            "content": {
                "application/json": {},
                "text/plain": {},
                "application/x-subrip": {},
                "text/vtt": {},
            },
        },
        400: {"description": "Invalid URL or parameters"},
        404: {"description": "Video not found or no transcript for the language"},
        500: {"description": "Server error"},
    },
)
async def get_transcript(
    url: str = Query(..., description="Video URL"),  # noqa: B008
    lang: str = Query(  # noqa: B008
        "en",
        pattern=r"^[a-zA-Z]{2,3}(-[a-zA-Z0-9]{2,8})?$",
        description="Subtitle language code (e.g. en, it, pt-BR)",
    ),
    source: str = Query(  # noqa: B008
        "any",
        pattern=r"^(any|manual|auto)$",
        description="Transcript source: manual subtitles, auto-captions, or any",
    ),
    fmt: str = Query(  # noqa: B008
        "json",
        pattern=r"^(json|text|srt|vtt)$",
        description="Output format",
    ),
    provider_manager: ProviderManager = Depends(get_provider_manager),  # noqa: B008
) -> Any:
    """
    Get the transcript of a video without downloading media.

    Fetches manual subtitles or auto-generated captions for the requested
    language and returns them as timed segments (json), plain text, SRT,
    or the raw VTT file.

    Args:
        url: Video URL
        lang: Subtitle language code
        source: Preferred transcript source
        fmt: Output format
        provider_manager: Provider manager instance

    Returns:
        Transcript in the requested format

    Raises:
        HTTPException: If URL is invalid, video unavailable, or no
            transcript exists for the language
    """
    logger.info("transcript_requested", url=url, lang=lang, source=source, fmt=fmt)

    # Validate URL
    validation = url_validator.validate(url)
    if not validation.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_URL",
                "message": validation.error_message,
            },
        )

    try:
        provider = provider_manager.get_provider_for_url(url)

        transcript = await provider.get_transcript(url=url, lang=lang, source=source)

        return _render_transcript(fmt, transcript)

    except InvalidURLError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_URL",
                "message": str(e),
            },
        )
    except TranscriptNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "TRANSCRIPT_NOT_FOUND",
                "message": str(e),
            },
        )
    except VideoUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "VIDEO_UNAVAILABLE",
                "message": str(e),
            },
        )
    except ProviderError as e:
        logger.error("provider_error", url=url, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "PROVIDER_ERROR",
                "message": str(e),
            },
        )
    except Exception as e:
        logger.error("unexpected_error", url=url, error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
            },
        )
