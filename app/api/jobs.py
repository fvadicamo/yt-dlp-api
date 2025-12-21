"""Job status API endpoint.

This module implements requirement 15: Job Status Tracking.
- GET /api/v1/jobs/{job_id}
"""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas import JobStatusResponse
from app.middleware.auth import require_api_key
from app.services.download_queue import DownloadQueue
from app.services.job_service import JobNotFoundError, JobService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["jobs"])


# Dependency placeholders (to be configured in main app)
async def get_job_service() -> JobService:
    """Get job service instance."""
    raise NotImplementedError("Job service dependency not configured")


async def get_download_queue() -> DownloadQueue:
    """Get download queue instance."""
    raise NotImplementedError("Download queue dependency not configured")


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    dependencies=[Depends(require_api_key)],
    responses={
        404: {"description": "Job not found"},
        500: {"description": "Server error"},
    },
)
async def get_job_status(
    job_id: str,
    job_service: JobService = Depends(get_job_service),  # noqa: B008
    download_queue: DownloadQueue = Depends(get_download_queue),  # noqa: B008
) -> Any:
    """
    Get job status.

    Returns the current status of a download job including:
    - Status (pending, processing, retrying, completed, failed)
    - Progress percentage (0-100)
    - Queue position (if pending)
    - File path and size (if completed)
    - Error message (if failed)

    Args:
        job_id: Job unique identifier
        job_service: Job service instance
        download_queue: Download queue instance

    Returns:
        Job status information

    Raises:
        HTTPException: If job is not found
    """
    logger.debug("job_status_requested", job_id=job_id)

    try:
        job = job_service.get_job_or_raise(job_id)
    except JobNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "JOB_NOT_FOUND",
                "message": f"Job not found: {job_id}",
            },
        )

    # Get queue position if job is pending
    queue_position = None
    if job.status.value == "pending":
        queue_position = download_queue.get_queue_position(job_id)

    response = JobStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        url=job.url,
        progress=job.progress,
        retry_count=job.retry_count,
        error_message=job.error_message,
        file_path=job.file_path,
        file_size=job.file_size,
        duration=job.duration,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        queue_position=queue_position or job.queue_position,
    )

    logger.debug(
        "job_status_retrieved",
        job_id=job_id,
        status=job.status.value,
    )

    return response
