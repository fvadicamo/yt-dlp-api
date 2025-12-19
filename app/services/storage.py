"""Storage management with cleanup, disk monitoring, and file size limits.

This module implements requirements 22, 24, and 25:
- Req 22: Output directory management
- Req 24: Automatic cleanup with age-based retention
- Req 25: File size limits enforcement
"""

import asyncio
import os
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Set

import structlog

from app.core.config import StorageConfig

logger = structlog.get_logger(__name__)


@dataclass
class DiskUsage:
    """Disk usage statistics."""

    total: int
    used: int
    available: int
    percent_used: float


@dataclass
class CleanupResult:
    """Result of a cleanup operation."""

    files_deleted: int
    bytes_reclaimed: int
    files_preserved: int
    dry_run: bool


class StorageError(Exception):
    """Exception raised for storage-related errors."""

    pass


class StorageManager:
    """Manages storage, cleanup, and file size validation.

    This class handles:
    - Output directory initialization and permission verification
    - Disk usage monitoring
    - Active job file tracking to prevent deletion
    - Automatic cleanup of old files
    - File size validation before downloads
    """

    def __init__(self, config: StorageConfig) -> None:
        """Initialize the storage manager.

        Args:
            config: Storage configuration with paths and limits.
        """
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.cleanup_age_hours = config.cleanup_age
        self.cleanup_threshold = config.cleanup_threshold
        self.max_file_size = config.max_file_size

        # Track files belonging to active jobs (job_id -> set of filepaths)
        self._active_jobs: Dict[str, Set[Path]] = {}

        logger.debug(
            "storage_manager_initialized",
            output_dir=str(self.output_dir),
            cleanup_age_hours=self.cleanup_age_hours,
            cleanup_threshold=self.cleanup_threshold,
            max_file_size=self.max_file_size,
        )

    def initialize(self) -> None:
        """Initialize the output directory.

        Creates the directory if it doesn't exist and verifies write permissions.

        Raises:
            StorageError: If directory creation fails or permissions are insufficient.
        """
        try:
            # Create directory if it doesn't exist
            if not self.output_dir.exists():
                self.output_dir.mkdir(parents=True, exist_ok=True)
                logger.info("output_directory_created", path=str(self.output_dir))

            # Verify write permissions by creating a test file with unique name
            # to avoid race conditions in multi-worker scenarios
            test_file = self.output_dir / f".write_test_{os.getpid()}_{uuid.uuid4().hex}"
            try:
                test_file.touch()
                test_file.unlink(missing_ok=True)
            except PermissionError as e:
                raise StorageError(
                    f"Insufficient permissions to write to output directory: {self.output_dir}"
                ) from e

            logger.info(
                "storage_initialized",
                output_dir=str(self.output_dir),
                writable=True,
            )

        except OSError as e:
            raise StorageError(f"Failed to initialize output directory: {e}") from e

    def get_disk_usage(self) -> DiskUsage:
        """Get current disk usage for the output directory.

        Returns:
            DiskUsage object with total, used, available bytes and percentage.
        """
        try:
            usage = shutil.disk_usage(self.output_dir)
            percent_used = (usage.used / usage.total) * 100 if usage.total > 0 else 0.0

            return DiskUsage(
                total=usage.total,
                used=usage.used,
                available=usage.free,
                percent_used=round(percent_used, 2),
            )
        except OSError as e:
            logger.error("disk_usage_check_failed", error=str(e))
            raise StorageError(f"Failed to get disk usage: {e}") from e

    def should_cleanup(self) -> bool:
        """Check if cleanup should be triggered based on disk usage threshold.

        Returns:
            True if disk usage exceeds the configured threshold.
        """
        try:
            usage = self.get_disk_usage()
            should_run = usage.percent_used >= self.cleanup_threshold

            if should_run:
                logger.info(
                    "cleanup_threshold_exceeded",
                    disk_usage_percent=usage.percent_used,
                    threshold=self.cleanup_threshold,
                )

            return should_run
        except StorageError:
            # If we can't check disk usage, don't trigger cleanup
            return False

    def register_active_job(self, job_id: str, filepath: Path) -> None:
        """Register a file as belonging to an active job.

        Files registered to active jobs will be preserved during cleanup.

        Args:
            job_id: Unique identifier for the job.
            filepath: Path to the file to protect.
        """
        if job_id not in self._active_jobs:
            self._active_jobs[job_id] = set()

        # Resolve to absolute path for consistent comparison
        abs_path = filepath.resolve()
        self._active_jobs[job_id].add(abs_path)

        logger.debug(
            "file_registered_to_job",
            job_id=job_id,
            filepath=str(abs_path),
        )

    def unregister_active_job(self, job_id: str) -> None:
        """Unregister all files for a job, allowing them to be cleaned up.

        Args:
            job_id: Unique identifier for the job.
        """
        if job_id in self._active_jobs:
            file_count = len(self._active_jobs[job_id])
            del self._active_jobs[job_id]
            logger.debug(
                "job_unregistered",
                job_id=job_id,
                files_released=file_count,
            )

    def is_file_active(self, filepath: Path) -> bool:
        """Check if a file belongs to an active job.

        Args:
            filepath: Path to check.

        Returns:
            True if the file is registered to any active job.
        """
        abs_path = filepath.resolve()
        return any(abs_path in files for files in self._active_jobs.values())

    def get_active_job_count(self) -> int:
        """Get the number of active jobs with registered files.

        Returns:
            Number of active jobs.
        """
        return len(self._active_jobs)

    def validate_file_size(self, estimated_size: int) -> bool:
        """Validate if a file size is within the configured limit.

        Args:
            estimated_size: Estimated file size in bytes.

        Returns:
            True if the size is within limits, False otherwise.
        """
        if estimated_size <= 0:
            # Unknown or zero size, allow the download
            return True

        is_valid = estimated_size <= self.max_file_size

        if not is_valid:
            logger.warning(
                "file_size_limit_exceeded",
                estimated_size=estimated_size,
                max_size=self.max_file_size,
                estimated_mb=round(estimated_size / (1024 * 1024), 2),
                max_mb=round(self.max_file_size / (1024 * 1024), 2),
            )

        return is_valid

    def cleanup_old_files(self, dry_run: bool = False) -> CleanupResult:
        """Remove files older than the configured retention period.

        Files belonging to active jobs are preserved regardless of age.

        Args:
            dry_run: If True, only report what would be deleted without deleting.

        Returns:
            CleanupResult with statistics about the cleanup operation.
        """
        files_deleted = 0
        bytes_reclaimed = 0
        files_preserved = 0

        current_time = time.time()
        max_age_seconds = self.cleanup_age_hours * 3600

        log_prefix = "[DRY-RUN] " if dry_run else ""

        logger.info(
            f"{log_prefix}cleanup_started",
            output_dir=str(self.output_dir),
            max_age_hours=self.cleanup_age_hours,
            dry_run=dry_run,
        )

        try:
            # Iterate over all files in the output directory
            for filepath in self.output_dir.iterdir():
                # Skip directories and hidden files
                if filepath.is_dir() or filepath.name.startswith("."):
                    continue

                try:
                    stat = filepath.stat()
                    file_age_seconds = current_time - stat.st_mtime
                    file_age_hours = file_age_seconds / 3600
                    file_size = stat.st_size

                    # Check if file is old enough for cleanup
                    if file_age_seconds < max_age_seconds:
                        continue

                    # Check if file belongs to an active job
                    if self.is_file_active(filepath):
                        files_preserved += 1
                        logger.debug(
                            f"{log_prefix}file_preserved_active_job",
                            filepath=str(filepath),
                            age_hours=round(file_age_hours, 2),
                        )
                        continue

                    # Delete the file (or simulate in dry-run)
                    if not dry_run:
                        filepath.unlink()

                    files_deleted += 1
                    bytes_reclaimed += file_size

                    logger.info(
                        f"{log_prefix}file_deleted",
                        filepath=str(filepath),
                        size_bytes=file_size,
                        size_mb=round(file_size / (1024 * 1024), 2),
                        age_hours=round(file_age_hours, 2),
                    )

                except OSError as e:
                    logger.warning(
                        "file_cleanup_failed",
                        filepath=str(filepath),
                        error=str(e),
                    )

        except OSError as e:
            logger.error("cleanup_directory_access_failed", error=str(e))

        result = CleanupResult(
            files_deleted=files_deleted,
            bytes_reclaimed=bytes_reclaimed,
            files_preserved=files_preserved,
            dry_run=dry_run,
        )

        logger.info(
            f"{log_prefix}cleanup_completed",
            files_deleted=files_deleted,
            bytes_reclaimed=bytes_reclaimed,
            bytes_reclaimed_mb=round(bytes_reclaimed / (1024 * 1024), 2),
            files_preserved=files_preserved,
            dry_run=dry_run,
        )

        return result

    def get_output_path(self, filename: str) -> Path:
        """Get the full path for a file in the output directory.

        Args:
            filename: Name of the file.

        Returns:
            Full path to the file in the output directory.
        """
        return self.output_dir / filename


async def cleanup_scheduler(
    storage: StorageManager,
    interval: int = 3600,
    run_once: bool = False,
) -> Optional[CleanupResult]:
    """Run periodic cleanup checks.

    This function runs in the background and triggers cleanup when the
    disk usage threshold is exceeded.

    Args:
        storage: StorageManager instance to use for cleanup.
        interval: Seconds between cleanup checks (default: 1 hour).
        run_once: If True, run only one cleanup cycle (for testing).

    Returns:
        CleanupResult if run_once is True and cleanup was performed, None otherwise.
    """
    logger.info(
        "cleanup_scheduler_started",
        interval_seconds=interval,
        interval_hours=interval / 3600,
    )

    while True:
        await asyncio.sleep(interval)

        if storage.should_cleanup():
            result = storage.cleanup_old_files()
            logger.info(
                "scheduled_cleanup_completed",
                files_deleted=result.files_deleted,
                bytes_reclaimed=result.bytes_reclaimed,
            )

            if run_once:
                return result
        else:
            logger.debug("cleanup_not_needed", reason="threshold_not_exceeded")

            if run_once:
                return None


# Global storage manager instance
_storage_manager: Optional[StorageManager] = None


def configure_storage(config: StorageConfig) -> StorageManager:
    """Configure and initialize the global storage manager.

    Args:
        config: Storage configuration.

    Returns:
        Configured StorageManager instance.
    """
    global _storage_manager
    _storage_manager = StorageManager(config)
    _storage_manager.initialize()
    return _storage_manager


def get_storage_manager() -> StorageManager:
    """Get the global storage manager instance.

    Returns:
        The configured StorageManager.

    Raises:
        RuntimeError: If storage manager is not configured.
    """
    if _storage_manager is None:
        raise RuntimeError("Storage manager not configured. Call configure_storage() first.")
    return _storage_manager
