"""Service layer implementations."""

from app.services.cookie_service import CookieService
from app.services.download_queue import (
    PRIORITY_DOWNLOAD,
    PRIORITY_METADATA,
    DownloadQueue,
    QueuedJob,
    configure_download_queue,
    get_download_queue,
)
from app.services.download_worker import (
    DownloadWorker,
    configure_download_worker,
    get_download_worker,
    start_download_worker,
    stop_download_worker,
)
from app.services.job_service import (
    JobNotFoundError,
    JobService,
    configure_job_service,
    get_job_service,
    job_cleanup_scheduler,
)
from app.services.storage import (
    CleanupResult,
    DiskUsage,
    StorageError,
    StorageManager,
    cleanup_scheduler,
    configure_storage,
    get_storage_manager,
)

__all__ = [
    # Cookie service
    "CookieService",
    # Job service
    "JobNotFoundError",
    "JobService",
    "configure_job_service",
    "get_job_service",
    "job_cleanup_scheduler",
    # Download queue
    "PRIORITY_DOWNLOAD",
    "PRIORITY_METADATA",
    "DownloadQueue",
    "QueuedJob",
    "configure_download_queue",
    "get_download_queue",
    # Download worker
    "DownloadWorker",
    "configure_download_worker",
    "get_download_worker",
    "start_download_worker",
    "stop_download_worker",
    # Storage
    "CleanupResult",
    "DiskUsage",
    "StorageError",
    "StorageManager",
    "cleanup_scheduler",
    "configure_storage",
    "get_storage_manager",
]
