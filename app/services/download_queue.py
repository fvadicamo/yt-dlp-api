"""Download queue with priority and concurrency control.

This module implements requirements 26 and 29:
- Req 26: Concurrent Downloads
  - Priority queue (metadata priority 1, download priority 10)
  - Configurable max concurrent downloads (default 5)
  - Queue position tracking
- Req 29: Queue metrics collection
"""

import asyncio
import heapq
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

import structlog

from app.core.metrics import MetricsCollector

logger = structlog.get_logger(__name__)


# Priority constants
PRIORITY_METADATA = 1  # High priority for fast metadata operations
PRIORITY_DOWNLOAD = 10  # Normal priority for downloads


@dataclass(order=True)
class QueuedJob:
    """A job in the download queue with priority ordering.

    Lower priority number = higher priority (processed first).
    """

    priority: int
    enqueue_time: float = field(compare=True)  # Secondary sort by enqueue time
    job_id: str = field(compare=False)


class DownloadQueue:
    """Priority queue for managing download jobs with concurrency control.

    Features:
    - Priority-based ordering (metadata > downloads)
    - FIFO within same priority level
    - Configurable max concurrent downloads
    - Queue position tracking
    """

    def __init__(
        self,
        max_concurrent: int = 5,
        max_queue_size: int = 100,
    ) -> None:
        """Initialize the download queue.

        Args:
            max_concurrent: Maximum number of concurrent downloads.
            max_queue_size: Maximum queue size (0 = unlimited).
        """
        self.max_concurrent = max_concurrent
        self.max_queue_size = max_queue_size

        self._queue: List[QueuedJob] = []
        self._active_jobs: Set[str] = set()
        self._job_positions: Dict[str, int] = {}  # job_id -> position in queue
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._lock = asyncio.Lock()

        logger.debug(
            "download_queue_initialized",
            max_concurrent=max_concurrent,
            max_queue_size=max_queue_size,
        )

    async def enqueue(
        self,
        job_id: str,
        priority: int = PRIORITY_DOWNLOAD,
    ) -> int:
        """Add a job to the queue.

        Args:
            job_id: The job's unique identifier.
            priority: Priority level (lower = higher priority).

        Returns:
            Position in the queue (1-indexed).

        Raises:
            ValueError: If queue is full.
        """
        async with self._lock:
            # Check queue size limit
            if self.max_queue_size > 0 and len(self._queue) >= self.max_queue_size:
                raise ValueError(
                    f"Queue is full (max {self.max_queue_size} jobs). " "Please try again later."
                )

            # Check if job is already queued
            if job_id in self._job_positions:
                logger.warning(
                    "job_already_queued",
                    job_id=job_id,
                )
                return self._job_positions[job_id]

            # Create queue entry
            queued_job = QueuedJob(
                priority=priority,
                enqueue_time=time.time(),
                job_id=job_id,
            )

            heapq.heappush(self._queue, queued_job)
            self._update_positions()

            position = self._job_positions[job_id]

            logger.info(
                "job_enqueued",
                job_id=job_id,
                priority=priority,
                queue_position=position,
                queue_size=len(self._queue),
            )

            # Update queue metrics
            self._update_metrics()

            return position

    async def dequeue(self) -> Optional[str]:
        """Get the next job from the queue.

        This method acquires a semaphore slot before returning a job.
        The caller should call `release_slot()` when done processing.

        Returns:
            Job ID if available, None if queue is empty.
        """
        # Try to acquire a slot (non-blocking check first)
        if self._semaphore.locked():
            # All slots are in use, can't dequeue
            return None

        await self._semaphore.acquire()

        async with self._lock:
            if not self._queue:
                # No jobs available, release the slot
                self._semaphore.release()
                return None

            queued_job = heapq.heappop(self._queue)
            job_id = queued_job.job_id

            # Track as active
            self._active_jobs.add(job_id)

            # Update positions for remaining jobs
            if job_id in self._job_positions:
                del self._job_positions[job_id]
            self._update_positions()

            logger.info(
                "job_dequeued",
                job_id=job_id,
                priority=queued_job.priority,
                active_count=len(self._active_jobs),
                remaining_queue_size=len(self._queue),
            )

            # Update queue metrics
            self._update_metrics()

            return job_id

    async def release_slot(self, job_id: str) -> None:
        """Release a download slot after processing completes.

        Args:
            job_id: The job's unique identifier.
        """
        async with self._lock:
            if job_id in self._active_jobs:
                self._active_jobs.remove(job_id)

            self._semaphore.release()

            logger.debug(
                "download_slot_released",
                job_id=job_id,
                active_count=len(self._active_jobs),
            )

            # Update queue metrics
            self._update_metrics()

    async def acquire_slot_for_sync(self, job_id: str, timeout: float = 0.0) -> bool:
        """Try to acquire a download slot for synchronous processing.

        This method is used for sync downloads to respect concurrency limits.
        Unlike enqueue, it doesn't add the job to the queue, just acquires a slot.

        Args:
            job_id: The job's unique identifier.
            timeout: Maximum time to wait for a slot (0 = non-blocking).

        Returns:
            True if slot was acquired, False if no slots available.
        """
        try:
            if timeout > 0:
                await asyncio.wait_for(self._semaphore.acquire(), timeout=timeout)
            else:
                # Non-blocking acquire
                if not self._semaphore.locked():
                    await self._semaphore.acquire()
                else:
                    return False

            async with self._lock:
                self._active_jobs.add(job_id)

            logger.debug(
                "sync_slot_acquired",
                job_id=job_id,
                active_count=len(self._active_jobs),
            )
            return True

        except asyncio.TimeoutError:
            return False

    def _update_positions(self) -> None:
        """Update queue positions for all jobs.

        Must be called with lock held.
        """
        # Sort queue to get correct order
        sorted_queue = sorted(self._queue)

        self._job_positions.clear()
        for idx, queued_job in enumerate(sorted_queue):
            self._job_positions[queued_job.job_id] = idx + 1  # 1-indexed

    def _update_metrics(self) -> None:
        """Update Prometheus queue metrics.

        Must be called with lock held.
        """
        MetricsCollector.update_queue_metrics(
            queue_size=len(self._queue),
            active_downloads=len(self._active_jobs),
        )

    def get_queue_position(self, job_id: str) -> Optional[int]:
        """Get a job's position in the queue.

        Args:
            job_id: The job's unique identifier.

        Returns:
            Queue position (1-indexed) if queued, None if not in queue.
        """
        return self._job_positions.get(job_id)

    def is_active(self, job_id: str) -> bool:
        """Check if a job is currently being processed.

        Args:
            job_id: The job's unique identifier.

        Returns:
            True if the job is active (dequeued and processing).
        """
        return job_id in self._active_jobs

    def get_queue_size(self) -> int:
        """Get the current queue size (waiting jobs).

        Returns:
            Number of jobs waiting in the queue.
        """
        return len(self._queue)

    def get_active_count(self) -> int:
        """Get the number of active (processing) jobs.

        Returns:
            Number of jobs currently being processed.
        """
        return len(self._active_jobs)

    def get_available_slots(self) -> int:
        """Get the number of available download slots.

        Returns:
            Number of available slots.
        """
        return self.max_concurrent - len(self._active_jobs)

    async def remove_job(self, job_id: str) -> bool:
        """Remove a job from the queue (if not yet processing).

        Args:
            job_id: The job's unique identifier.

        Returns:
            True if the job was removed, False if not found or already active.
        """
        async with self._lock:
            # Can't remove active jobs
            if job_id in self._active_jobs:
                return False

            # Find and remove from queue
            original_len = len(self._queue)
            self._queue = [qj for qj in self._queue if qj.job_id != job_id]

            if len(self._queue) < original_len:
                heapq.heapify(self._queue)
                if job_id in self._job_positions:
                    del self._job_positions[job_id]
                self._update_positions()

                logger.info(
                    "job_removed_from_queue",
                    job_id=job_id,
                )
                return True

            return False

    def get_stats(self) -> Dict[str, int]:
        """Get queue statistics.

        Returns:
            Dictionary with queue statistics.
        """
        return {
            "queue_size": len(self._queue),
            "active_count": len(self._active_jobs),
            "available_slots": self.get_available_slots(),
            "max_concurrent": self.max_concurrent,
        }


# Global download queue instance
_download_queue: Optional[DownloadQueue] = None


def configure_download_queue(
    max_concurrent: int = 5,
    max_queue_size: int = 100,
) -> DownloadQueue:
    """Configure and initialize the global download queue.

    Args:
        max_concurrent: Maximum number of concurrent downloads.
        max_queue_size: Maximum queue size.

    Returns:
        Configured DownloadQueue instance.
    """
    global _download_queue
    _download_queue = DownloadQueue(
        max_concurrent=max_concurrent,
        max_queue_size=max_queue_size,
    )
    return _download_queue


def get_download_queue() -> DownloadQueue:
    """Get the global download queue instance.

    Returns:
        The configured DownloadQueue.

    Raises:
        RuntimeError: If download queue is not configured.
    """
    if _download_queue is None:
        raise RuntimeError("Download queue not configured. Call configure_download_queue() first.")
    return _download_queue
