"""Download worker for processing queued download jobs.

This module implements requirements 14, 15, 26, and 29:
- Req 14: Download endpoint with async job support
- Req 15: Job status tracking with progress
- Req 26: Concurrent download management
- Req 29: Download metrics collection
"""

import asyncio
import contextlib
import time
from pathlib import Path
from typing import Optional

import structlog

from app.core.metrics import MetricsCollector
from app.models.video import DownloadResult
from app.providers.base import VideoProvider
from app.providers.exceptions import DownloadError, ProviderError
from app.providers.manager import ProviderManager
from app.services.download_queue import DownloadQueue, get_download_queue
from app.services.job_service import JobService, get_job_service
from app.services.storage import StorageManager, get_storage_manager

logger = structlog.get_logger(__name__)


class DownloadWorker:
    """Worker that processes download jobs from the queue.

    Handles job lifecycle:
    - Dequeue jobs when capacity available
    - Execute downloads via provider
    - Handle retries on retriable errors
    - Update job status and progress
    - Register/unregister files with storage manager
    """

    def __init__(
        self,
        provider_manager: ProviderManager,
        job_service: Optional[JobService] = None,
        download_queue: Optional[DownloadQueue] = None,
        storage_manager: Optional[StorageManager] = None,
        poll_interval: float = 1.0,
    ) -> None:
        """Initialize the download worker.

        Args:
            provider_manager: Provider manager for executing downloads.
            job_service: Job service for status updates (uses global if None).
            download_queue: Download queue (uses global if None).
            storage_manager: Storage manager for file tracking (uses global if None).
            poll_interval: Seconds between queue polling attempts.
        """
        self.provider_manager = provider_manager
        self._job_service = job_service
        self._download_queue = download_queue
        self._storage_manager = storage_manager
        self.poll_interval = poll_interval
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

        logger.debug(
            "download_worker_initialized",
            poll_interval=poll_interval,
        )

    @property
    def job_service(self) -> JobService:
        """Get the job service instance."""
        return self._job_service or get_job_service()

    @property
    def download_queue(self) -> DownloadQueue:
        """Get the download queue instance."""
        return self._download_queue or get_download_queue()

    @property
    def storage_manager(self) -> StorageManager:
        """Get the storage manager instance."""
        return self._storage_manager or get_storage_manager()

    async def start(self) -> None:
        """Start the download worker.

        The worker runs in the background, polling for jobs
        and processing them as capacity becomes available.
        """
        if self._running:
            logger.warning("download_worker_already_running")
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._run())

        logger.info("download_worker_started")

    async def stop(self) -> None:
        """Stop the download worker gracefully.

        Waits for current downloads to complete before stopping.
        """
        if not self._running:
            return

        self._running = False

        if self._worker_task:
            self._worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task
            self._worker_task = None

        logger.info("download_worker_stopped")

    async def _run(self) -> None:
        """Main worker loop."""
        logger.info("download_worker_loop_started")

        while self._running:
            try:
                # Try to dequeue a job
                job_id = await self.download_queue.dequeue()

                if job_id:
                    # Process the job in a separate task
                    asyncio.create_task(self._process_job(job_id))
                else:
                    # No job available, wait before polling again
                    await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(
                    "download_worker_loop_error",
                    error=str(e),
                    exc_info=True,
                )
                await asyncio.sleep(self.poll_interval)

    async def _process_job(self, job_id: str) -> None:
        """Process a single download job.

        Args:
            job_id: The job's unique identifier.
        """
        job = self.job_service.get_job(job_id)
        if not job:
            logger.error("job_not_found_for_processing", job_id=job_id)
            await self.download_queue.release_slot(job_id)
            return

        logger.info(
            "job_processing_started",
            job_id=job_id,
            url=job.url,
            retry_count=job.retry_count,
        )

        # Track download metrics (default to failed, updated on success)
        start_time = time.time()
        provider_name = "youtube"  # Default provider name
        download_status = "failed"
        download_size = 0

        try:
            # Update status to PROCESSING
            self.job_service.start_processing(job_id)

            # Get the appropriate provider for the URL
            provider = self.provider_manager.get_provider_for_url(job.url)
            provider_name = getattr(provider, "name", "youtube")

            # Execute the download
            result = await self._execute_download(job_id, provider)

            if result:
                # Download succeeded - update metrics tracking
                download_status = "success"
                download_size = result.file_size

                file_path = Path(result.file_path)

                # Register the file with storage manager
                self.storage_manager.register_active_job(job_id, file_path)

                # Complete the job
                self.job_service.complete_job(
                    job_id=job_id,
                    file_path=result.file_path,
                    file_size=result.file_size,
                    duration=result.duration,
                )

                logger.info(
                    "job_completed_successfully",
                    job_id=job_id,
                    file_path=result.file_path,
                    file_size=result.file_size,
                    duration=result.duration,
                )

        except DownloadError as e:
            await self._handle_download_error(job_id, e)

        except ProviderError as e:
            # Non-retriable provider error
            self.job_service.fail_job(job_id, str(e))
            logger.error(
                "job_failed_provider_error",
                job_id=job_id,
                error=str(e),
            )

        except Exception as e:
            # Unexpected error
            self.job_service.fail_job(job_id, f"Unexpected error: {str(e)}")
            logger.error(
                "job_failed_unexpected_error",
                job_id=job_id,
                error=str(e),
                exc_info=True,
            )

        finally:
            # Record metrics once in finally block (reduces duplication)
            download_duration = time.time() - start_time
            MetricsCollector.record_download(
                provider=provider_name,
                status=download_status,
                duration=download_duration,
                size=download_size,
            )
            # Release the download slot
            await self.download_queue.release_slot(job_id)

    async def _execute_download(
        self,
        job_id: str,
        provider: VideoProvider,
    ) -> DownloadResult:
        """Execute the download operation.

        Args:
            job_id: The job's unique identifier.
            provider: The provider to use for download.

        Returns:
            DownloadResult on success.

        Raises:
            DownloadError: If download fails.
            ProviderError: If provider error occurs.
        """
        job = self.job_service.get_job(job_id)
        if not job:
            raise ProviderError(f"Job not found: {job_id}")

        params = job.params

        # Execute download with parameters
        result = await provider.download(
            url=job.url,
            format_id=params.get("format_id"),
            output_template=params.get("output_template"),
            extract_audio=params.get("extract_audio", False),
            audio_format=params.get("audio_format"),
            include_subtitles=params.get("include_subtitles", False),
            subtitle_lang=params.get("subtitle_lang"),
        )

        return result

    async def _handle_download_error(
        self,
        job_id: str,
        error: DownloadError,
    ) -> None:
        """Handle a download error, potentially retrying.

        Args:
            job_id: The job's unique identifier.
            error: The download error that occurred.
        """
        job = self.job_service.get_job(job_id)
        if not job:
            return

        # Check if we can retry
        if job.can_retry():
            # Mark as retrying
            self.job_service.start_retry(job_id)

            logger.warning(
                "job_retrying",
                job_id=job_id,
                retry_count=job.retry_count,
                max_retries=job.max_retries,
                error=str(error),
            )

            # Re-queue the job for retry
            # Use same priority to maintain fairness
            try:
                await self.download_queue.enqueue(job_id)
            except ValueError as queue_error:
                # Queue is full, fail the job instead of leaving it in RETRYING
                self.job_service.fail_job(
                    job_id,
                    f"Retry failed: queue full. Original error: {str(error)}",
                )
                logger.error(
                    "job_retry_failed_queue_full",
                    job_id=job_id,
                    retry_count=job.retry_count,
                    queue_error=str(queue_error),
                    original_error=str(error),
                )
                return

        else:
            # Max retries exceeded
            self.job_service.fail_job(
                job_id,
                f"Max retries ({job.max_retries}) exceeded. Last error: {str(error)}",
            )

            logger.error(
                "job_failed_max_retries",
                job_id=job_id,
                retry_count=job.retry_count,
                error=str(error),
            )

    async def process_single_job(self, job_id: str) -> None:
        """Process a single job synchronously (for testing or sync mode).

        This method directly processes a job without going through the queue.

        Args:
            job_id: The job's unique identifier.
        """
        await self._process_job(job_id)


# Global download worker instance
_download_worker: Optional[DownloadWorker] = None


def configure_download_worker(
    provider_manager: ProviderManager,
    job_service: Optional[JobService] = None,
    download_queue: Optional[DownloadQueue] = None,
    storage_manager: Optional[StorageManager] = None,
    poll_interval: float = 1.0,
) -> DownloadWorker:
    """Configure and initialize the global download worker.

    Args:
        provider_manager: Provider manager for executing downloads.
        job_service: Job service for status updates.
        download_queue: Download queue.
        storage_manager: Storage manager for file tracking.
        poll_interval: Seconds between queue polling attempts.

    Returns:
        Configured DownloadWorker instance.
    """
    global _download_worker
    _download_worker = DownloadWorker(
        provider_manager=provider_manager,
        job_service=job_service,
        download_queue=download_queue,
        storage_manager=storage_manager,
        poll_interval=poll_interval,
    )
    return _download_worker


def get_download_worker() -> DownloadWorker:
    """Get the global download worker instance.

    Returns:
        The configured DownloadWorker.

    Raises:
        RuntimeError: If download worker is not configured.
    """
    if _download_worker is None:
        raise RuntimeError(
            "Download worker not configured. Call configure_download_worker() first."
        )
    return _download_worker


async def start_download_worker() -> None:
    """Start the global download worker."""
    worker = get_download_worker()
    await worker.start()


async def stop_download_worker() -> None:
    """Stop the global download worker."""
    worker = get_download_worker()
    await worker.stop()
