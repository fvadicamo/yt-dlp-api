"""Download API endpoint.

This module implements requirement 14: Download Endpoint.
- POST /api/v1/download with async and sync modes
"""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas import DownloadRequest, DownloadResponse, SyncDownloadResponse
from app.core.template import TemplateProcessor
from app.core.validation import FormatValidator, URLValidator
from app.middleware.auth import require_api_key
from app.models.job import JobStatus
from app.providers.exceptions import InvalidURLError
from app.providers.manager import ProviderManager
from app.services.download_queue import PRIORITY_DOWNLOAD, DownloadQueue
from app.services.download_worker import DownloadWorker
from app.services.job_service import JobService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["download"])

# Validators
url_validator = URLValidator()
format_validator = FormatValidator()
template_processor = TemplateProcessor()


# Dependency placeholders (to be configured in main app)
async def get_provider_manager() -> ProviderManager:
    """Get provider manager instance."""
    raise NotImplementedError("Provider manager dependency not configured")


async def get_job_service() -> JobService:
    """Get job service instance."""
    raise NotImplementedError("Job service dependency not configured")


async def get_download_queue() -> DownloadQueue:
    """Get download queue instance."""
    raise NotImplementedError("Download queue dependency not configured")


async def get_download_worker() -> DownloadWorker:
    """Get download worker instance."""
    raise NotImplementedError("Download worker dependency not configured")


@router.post(
    "/download",
    response_model=DownloadResponse,
    dependencies=[Depends(require_api_key)],
    responses={
        200: {"description": "Sync download completed", "model": SyncDownloadResponse},
        202: {"description": "Async download job created", "model": DownloadResponse},
        400: {"description": "Invalid request"},
        404: {"description": "Video not found"},
        500: {"description": "Server error"},
    },
)
async def download_video(  # noqa: C901
    request: DownloadRequest,
    provider_manager: ProviderManager = Depends(get_provider_manager),  # noqa: B008
    job_service: JobService = Depends(get_job_service),  # noqa: B008
    download_queue: DownloadQueue = Depends(get_download_queue),  # noqa: B008
    download_worker: DownloadWorker = Depends(get_download_worker),  # noqa: B008
) -> Any:
    """
    Download a video.

    Supports two modes:
    - async=true (default): Returns immediately with job_id for tracking
    - async=false: Waits for download to complete and returns result

    Args:
        request: Download request parameters
        provider_manager: Provider manager instance
        job_service: Job service instance
        download_queue: Download queue instance
        download_worker: Download worker instance

    Returns:
        DownloadResponse for async mode, SyncDownloadResponse for sync mode

    Raises:
        HTTPException: If request is invalid or download fails
    """
    logger.info(
        "download_requested",
        url=request.url,
        format_id=request.format_id,
        async_mode=request.async_mode,
    )

    # Validate URL
    url_validation = url_validator.validate(request.url)
    if not url_validation.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_URL",
                "message": url_validation.error_message,
            },
        )

    # Validate format ID if provided
    if request.format_id:
        format_validation = format_validator.validate_format_id(request.format_id)
        if not format_validation.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "INVALID_FORMAT",
                    "message": format_validation.error_message,
                },
            )

    # Validate output template if provided
    if request.output_template:
        template_result = template_processor.validate_template(request.output_template)
        if not template_result.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "INVALID_TEMPLATE",
                    "message": template_result.error_message,
                },
            )

    # Validate provider exists for URL
    try:
        provider_manager.get_provider_for_url(request.url)
    except InvalidURLError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_URL",
                "message": str(e),
            },
        )

    # Build job parameters
    params = {
        "format_id": request.format_id,
        "output_template": request.output_template,
        "extract_audio": request.extract_audio,
        "audio_format": request.audio_format,
        "include_subtitles": request.include_subtitles,
        "subtitle_lang": request.subtitle_lang,
    }

    # Create job
    job = job_service.create_job(url=request.url, params=params)

    if request.async_mode:
        # Async mode: enqueue and return immediately
        try:
            position = await download_queue.enqueue(job.job_id, priority=PRIORITY_DOWNLOAD)
            job_service.set_queue_position(job.job_id, position)
        except ValueError as e:
            # Queue is full
            job_service.fail_job(job.job_id, str(e))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error_code": "QUEUE_FULL",
                    "message": str(e),
                },
            )

        logger.info(
            "download_job_created",
            job_id=job.job_id,
            queue_position=position,
        )

        return DownloadResponse(
            job_id=job.job_id,
            status=job.status.value,
            created_at=job.created_at.isoformat(),
            queue_position=position,
            message="Download job created and queued",
        )

    else:
        # Sync mode: process immediately and wait for result
        logger.info("sync_download_started", job_id=job.job_id)

        try:
            # Process the job directly
            await download_worker.process_single_job(job.job_id)

            # Get updated job
            updated_job = job_service.get_job(job.job_id)

            if updated_job is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={
                        "error_code": "INTERNAL_ERROR",
                        "message": "Job not found after processing",
                    },
                )

            if updated_job.status == JobStatus.COMPLETED:
                logger.info(
                    "sync_download_completed",
                    job_id=job.job_id,
                    file_path=updated_job.file_path,
                )

                return SyncDownloadResponse(
                    file_path=updated_job.file_path or "",
                    file_size=updated_job.file_size or 0,
                    duration=updated_job.duration or 0.0,
                    format_id=request.format_id or "best",
                )

            elif updated_job.status == JobStatus.FAILED:
                error_message = updated_job.error_message or "Download failed"

                # Map error message to appropriate status code
                if "unavailable" in error_message.lower():
                    status_code = status.HTTP_404_NOT_FOUND
                    error_code = "VIDEO_UNAVAILABLE"
                elif "format" in error_message.lower():
                    status_code = status.HTTP_400_BAD_REQUEST
                    error_code = "FORMAT_NOT_FOUND"
                else:
                    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
                    error_code = "DOWNLOAD_FAILED"

                raise HTTPException(
                    status_code=status_code,
                    detail={
                        "error_code": error_code,
                        "message": error_message,
                    },
                )

            else:
                # Still processing (shouldn't happen in sync mode)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={
                        "error_code": "INTERNAL_ERROR",
                        "message": f"Unexpected job status: {updated_job.status.value}",
                    },
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "sync_download_error",
                job_id=job.job_id,
                error=str(e),
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error_code": "DOWNLOAD_FAILED",
                    "message": str(e),
                },
            )
