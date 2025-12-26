"""Job service for managing asynchronous download jobs.

This module implements requirement 15: Job Status Tracking.
- In-memory job storage with UUID generation
- Status updates and progress tracking
- 24-hour TTL for job history
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

import structlog

from app.models.job import Job, JobStatus

logger = structlog.get_logger(__name__)


class JobNotFoundError(Exception):
    """Raised when a job is not found."""

    pass


class JobService:
    """Service for managing download jobs.

    Provides CRUD operations for jobs with in-memory storage.
    Jobs are retained for a configurable TTL (default 24 hours).
    """

    def __init__(
        self,
        job_ttl_hours: int = 24,
        on_job_expired: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Initialize the job service.

        Args:
            job_ttl_hours: Time-to-live for completed/failed jobs in hours.
            on_job_expired: Optional callback called with job_id when a job expires.
                           Used to unregister files from StorageManager.
        """
        self.job_ttl_hours = job_ttl_hours
        self._jobs: Dict[str, Job] = {}
        self._on_job_expired = on_job_expired

        logger.debug(
            "job_service_initialized",
            job_ttl_hours=job_ttl_hours,
        )

    def create_job(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Job:
        """Create a new download job.

        Args:
            url: URL of the video to download.
            params: Download parameters (format_id, output_template, etc.).
            max_retries: Maximum number of retry attempts.

        Returns:
            The created Job object.
        """
        job_id = str(uuid.uuid4())
        job = Job(
            job_id=job_id,
            url=url,
            params=params or {},
            max_retries=max_retries,
            status=JobStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )

        self._jobs[job_id] = job

        logger.info(
            "job_created",
            job_id=job_id,
            url=url,
            params=params,
        )

        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID.

        Args:
            job_id: The job's unique identifier.

        Returns:
            The Job object if found, None otherwise.
        """
        return self._jobs.get(job_id)

    def get_job_or_raise(self, job_id: str) -> Job:
        """Get a job by ID or raise an error.

        Args:
            job_id: The job's unique identifier.

        Returns:
            The Job object.

        Raises:
            JobNotFoundError: If the job is not found.
        """
        job = self.get_job(job_id)
        if job is None:
            raise JobNotFoundError(f"Job not found: {job_id}")
        return job

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        **kwargs: Any,
    ) -> Job:
        """Update a job's status and optional fields.

        Args:
            job_id: The job's unique identifier.
            status: The new status.
            **kwargs: Additional fields to update (progress, error_message, etc.).

        Returns:
            The updated Job object.

        Raises:
            JobNotFoundError: If the job is not found.
        """
        job = self.get_job_or_raise(job_id)

        old_status = job.status
        job.status = status

        # Update timestamp based on status transition
        if status == JobStatus.PROCESSING and old_status == JobStatus.PENDING:
            job.started_at = datetime.now(timezone.utc)
        elif status in (JobStatus.COMPLETED, JobStatus.FAILED):
            job.completed_at = datetime.now(timezone.utc)

        # Update additional fields
        for key, value in kwargs.items():
            if hasattr(job, key):
                setattr(job, key, value)

        logger.info(
            "job_status_updated",
            job_id=job_id,
            old_status=old_status.value,
            new_status=status.value,
            **{k: v for k, v in kwargs.items() if k not in ("file_path",)},
        )

        return job

    def update_progress(self, job_id: str, progress: int) -> Job:
        """Update a job's progress percentage.

        Args:
            job_id: The job's unique identifier.
            progress: Progress percentage (0-100).

        Returns:
            The updated Job object.

        Raises:
            JobNotFoundError: If the job is not found.
        """
        job = self.get_job_or_raise(job_id)
        job.progress = max(0, min(100, progress))

        logger.debug(
            "job_progress_updated",
            job_id=job_id,
            progress=job.progress,
        )

        return job

    def start_processing(self, job_id: str) -> Job:
        """Mark a job as processing.

        Args:
            job_id: The job's unique identifier.

        Returns:
            The updated Job object.
        """
        return self.update_status(job_id, JobStatus.PROCESSING)

    def start_retry(self, job_id: str) -> Job:
        """Mark a job as retrying and increment retry count.

        Args:
            job_id: The job's unique identifier.

        Returns:
            The updated Job object.
        """
        job = self.get_job_or_raise(job_id)
        job.retry_count += 1

        return self.update_status(
            job_id,
            JobStatus.RETRYING,
            retry_count=job.retry_count,
        )

    def complete_job(
        self,
        job_id: str,
        file_path: str,
        file_size: int,
        duration: float,
    ) -> Job:
        """Mark a job as completed with result details.

        Args:
            job_id: The job's unique identifier.
            file_path: Path to the downloaded file.
            file_size: Size of the downloaded file in bytes.
            duration: Download duration in seconds.

        Returns:
            The updated Job object.
        """
        return self.update_status(
            job_id,
            JobStatus.COMPLETED,
            file_path=file_path,
            file_size=file_size,
            duration=duration,
            progress=100,
        )

    def fail_job(self, job_id: str, error_message: str) -> Job:
        """Mark a job as failed with an error message.

        Args:
            job_id: The job's unique identifier.
            error_message: Description of the failure.

        Returns:
            The updated Job object.
        """
        return self.update_status(
            job_id,
            JobStatus.FAILED,
            error_message=error_message,
        )

    def set_queue_position(self, job_id: str, position: int) -> Job:
        """Set a job's queue position.

        Args:
            job_id: The job's unique identifier.
            position: Position in the download queue.

        Returns:
            The updated Job object.
        """
        job = self.get_job_or_raise(job_id)
        job.queue_position = position

        logger.debug(
            "job_queue_position_updated",
            job_id=job_id,
            queue_position=position,
        )

        return job

    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: int = 100,
    ) -> List[Job]:
        """List jobs, optionally filtered by status.

        Args:
            status: Filter by job status (optional).
            limit: Maximum number of jobs to return.

        Returns:
            List of Job objects, sorted by creation time (newest first).
        """
        jobs = list(self._jobs.values())

        if status is not None:
            jobs = [j for j in jobs if j.status == status]

        # Sort by creation time (newest first)
        jobs.sort(key=lambda j: j.created_at, reverse=True)

        return jobs[:limit]

    def get_pending_jobs(self) -> List[Job]:
        """Get all pending jobs.

        Returns:
            List of pending Job objects.
        """
        return self.list_jobs(status=JobStatus.PENDING)

    def get_active_job_count(self) -> int:
        """Get the count of active jobs (pending, processing, or retrying).

        Returns:
            Number of active jobs.
        """
        active_statuses = {JobStatus.PENDING, JobStatus.PROCESSING, JobStatus.RETRYING}
        return sum(1 for job in self._jobs.values() if job.status in active_statuses)

    def cleanup_expired_jobs(self) -> int:
        """Remove jobs that have exceeded their TTL.

        Only completed and failed jobs are removed. Active jobs are preserved.

        Returns:
            Number of jobs removed.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.job_ttl_hours)
        terminal_statuses = {JobStatus.COMPLETED, JobStatus.FAILED}

        expired_ids = [
            job_id
            for job_id, job in self._jobs.items()
            if job.status in terminal_statuses
            and job.completed_at is not None
            and job.completed_at < cutoff
        ]

        for job_id in expired_ids:
            # Call expiration callback before deleting (for StorageManager cleanup)
            if self._on_job_expired is not None:
                self._on_job_expired(job_id)
            del self._jobs[job_id]

        if expired_ids:
            logger.info(
                "expired_jobs_cleaned",
                count=len(expired_ids),
                ttl_hours=self.job_ttl_hours,
            )

        return len(expired_ids)

    def get_job_count(self) -> int:
        """Get the total number of jobs.

        Returns:
            Total job count.
        """
        return len(self._jobs)


async def job_cleanup_scheduler(
    job_service: JobService,
    interval: int = 3600,
    run_once: bool = False,
) -> Optional[int]:
    """Run periodic job cleanup.

    Args:
        job_service: JobService instance to use for cleanup.
        interval: Seconds between cleanup runs (default: 1 hour).
        run_once: If True, run only one cleanup cycle (for testing).

    Returns:
        Number of jobs cleaned if run_once is True, None otherwise.
    """
    logger.info(
        "job_cleanup_scheduler_started",
        interval_seconds=interval,
        interval_hours=interval / 3600,
    )

    while True:
        await asyncio.sleep(interval)

        count = job_service.cleanup_expired_jobs()

        if count > 0:
            logger.info(
                "scheduled_job_cleanup_completed",
                jobs_removed=count,
            )

        if run_once:
            return count


# Global job service instance
_job_service: Optional[JobService] = None


def configure_job_service(
    job_ttl_hours: int = 24,
    on_job_expired: Optional[Callable[[str], None]] = None,
) -> JobService:
    """Configure and initialize the global job service.

    Args:
        job_ttl_hours: Time-to-live for completed/failed jobs in hours.
        on_job_expired: Optional callback called with job_id when a job expires.
                       Used to unregister files from StorageManager.

    Returns:
        Configured JobService instance.
    """
    global _job_service
    _job_service = JobService(
        job_ttl_hours=job_ttl_hours,
        on_job_expired=on_job_expired,
    )
    return _job_service


def get_job_service() -> JobService:
    """Get the global job service instance.

    Returns:
        The configured JobService.

    Raises:
        RuntimeError: If job service is not configured.
    """
    if _job_service is None:
        raise RuntimeError("Job service not configured. Call configure_job_service() first.")
    return _job_service
