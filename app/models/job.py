"""Job data models for asynchronous download tracking.

This module implements requirement 15: Job Status Tracking.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class JobStatus(str, Enum):
    """Status of a download job.

    State transitions:
    - PENDING -> PROCESSING: When worker picks up the job
    - PROCESSING -> COMPLETED: When download succeeds
    - PROCESSING -> RETRYING: When retriable error occurs
    - PROCESSING -> FAILED: When non-retriable error or max retries exceeded
    - RETRYING -> PROCESSING: When retry attempt starts
    - RETRYING -> FAILED: When max retries exceeded
    """

    PENDING = "pending"
    PROCESSING = "processing"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    """Represents an asynchronous download job.

    Tracks the lifecycle of a download operation from creation to completion.
    Jobs are stored in memory with a configurable TTL (default 24 hours).
    """

    job_id: str
    url: str
    status: JobStatus = JobStatus.PENDING
    params: Dict[str, Any] = field(default_factory=dict)
    progress: int = 0  # 0-100 percentage
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    duration: Optional[float] = None  # download duration in seconds
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    queue_position: Optional[int] = None

    def is_terminal(self) -> bool:
        """Check if the job is in a terminal state (completed or failed)."""
        return self.status in (JobStatus.COMPLETED, JobStatus.FAILED)

    def can_retry(self) -> bool:
        """Check if the job can be retried."""
        return self.retry_count < self.max_retries

    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary for API responses."""
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "url": self.url,
            "progress": self.progress,
            "retry_count": self.retry_count,
            "error_message": self.error_message,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "duration": self.duration,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "queue_position": self.queue_position,
        }
