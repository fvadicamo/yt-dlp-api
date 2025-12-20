"""Tests for job service."""

from datetime import datetime, timedelta

import pytest

from app.models.job import Job, JobStatus
from app.services.job_service import (
    JobNotFoundError,
    JobService,
    configure_job_service,
    get_job_service,
)


class TestJobModel:
    """Tests for Job dataclass."""

    def test_job_creation_with_defaults(self) -> None:
        """Test creating a job with default values."""
        job = Job(job_id="test-123", url="https://youtube.com/watch?v=abc")

        assert job.job_id == "test-123"
        assert job.url == "https://youtube.com/watch?v=abc"
        assert job.status == JobStatus.PENDING
        assert job.params == {}
        assert job.progress == 0
        assert job.retry_count == 0
        assert job.max_retries == 3
        assert job.error_message is None
        assert job.file_path is None
        assert job.file_size is None
        assert job.duration is None
        assert job.queue_position is None

    def test_job_is_terminal(self) -> None:
        """Test is_terminal method."""
        job = Job(job_id="test-123", url="https://youtube.com/watch?v=abc")

        # PENDING is not terminal
        assert not job.is_terminal()

        # PROCESSING is not terminal
        job.status = JobStatus.PROCESSING
        assert not job.is_terminal()

        # RETRYING is not terminal
        job.status = JobStatus.RETRYING
        assert not job.is_terminal()

        # COMPLETED is terminal
        job.status = JobStatus.COMPLETED
        assert job.is_terminal()

        # FAILED is terminal
        job.status = JobStatus.FAILED
        assert job.is_terminal()

    def test_job_can_retry(self) -> None:
        """Test can_retry method."""
        job = Job(job_id="test-123", url="https://youtube.com/watch?v=abc", max_retries=3)

        # Can retry when retry_count < max_retries
        assert job.can_retry()

        job.retry_count = 2
        assert job.can_retry()

        # Cannot retry when retry_count >= max_retries
        job.retry_count = 3
        assert not job.can_retry()

        job.retry_count = 4
        assert not job.can_retry()

    def test_job_to_dict(self) -> None:
        """Test to_dict method."""
        created = datetime(2024, 1, 15, 10, 30, 0)
        job = Job(
            job_id="test-123",
            url="https://youtube.com/watch?v=abc",
            status=JobStatus.COMPLETED,
            progress=100,
            created_at=created,
            completed_at=created + timedelta(seconds=45),
            file_path="/downloads/video.mp4",
            file_size=1024000,
            duration=45.2,
        )

        result = job.to_dict()

        assert result["job_id"] == "test-123"
        assert result["status"] == "completed"
        assert result["url"] == "https://youtube.com/watch?v=abc"
        assert result["progress"] == 100
        assert result["file_path"] == "/downloads/video.mp4"
        assert result["file_size"] == 1024000
        assert result["duration"] == 45.2
        assert result["created_at"] == "2024-01-15T10:30:00"
        assert result["completed_at"] == "2024-01-15T10:30:45"


class TestJobServiceCreation:
    """Tests for JobService job creation."""

    @pytest.fixture
    def job_service(self) -> JobService:
        """Create a fresh JobService instance."""
        return JobService(job_ttl_hours=24)

    def test_create_job(self, job_service: JobService) -> None:
        """Test creating a new job."""
        job = job_service.create_job(
            url="https://youtube.com/watch?v=abc",
            params={"format_id": "137"},
        )

        assert job.job_id is not None
        assert len(job.job_id) == 36  # UUID format
        assert job.url == "https://youtube.com/watch?v=abc"
        assert job.params == {"format_id": "137"}
        assert job.status == JobStatus.PENDING

    def test_create_job_with_max_retries(self, job_service: JobService) -> None:
        """Test creating a job with custom max retries."""
        job = job_service.create_job(
            url="https://youtube.com/watch?v=abc",
            max_retries=5,
        )

        assert job.max_retries == 5

    def test_create_multiple_jobs(self, job_service: JobService) -> None:
        """Test creating multiple jobs with unique IDs."""
        job1 = job_service.create_job(url="https://youtube.com/watch?v=abc")
        job2 = job_service.create_job(url="https://youtube.com/watch?v=def")

        assert job1.job_id != job2.job_id
        assert job_service.get_job_count() == 2


class TestJobServiceRetrieval:
    """Tests for JobService job retrieval."""

    @pytest.fixture
    def job_service(self) -> JobService:
        """Create a fresh JobService instance."""
        return JobService(job_ttl_hours=24)

    def test_get_job(self, job_service: JobService) -> None:
        """Test retrieving a job by ID."""
        job = job_service.create_job(url="https://youtube.com/watch?v=abc")

        retrieved = job_service.get_job(job.job_id)

        assert retrieved is not None
        assert retrieved.job_id == job.job_id

    def test_get_job_not_found(self, job_service: JobService) -> None:
        """Test retrieving a non-existent job."""
        retrieved = job_service.get_job("non-existent-id")

        assert retrieved is None

    def test_get_job_or_raise(self, job_service: JobService) -> None:
        """Test get_job_or_raise with existing job."""
        job = job_service.create_job(url="https://youtube.com/watch?v=abc")

        retrieved = job_service.get_job_or_raise(job.job_id)

        assert retrieved.job_id == job.job_id

    def test_get_job_or_raise_not_found(self, job_service: JobService) -> None:
        """Test get_job_or_raise with non-existent job."""
        with pytest.raises(JobNotFoundError, match="Job not found"):
            job_service.get_job_or_raise("non-existent-id")


class TestJobServiceStatusUpdates:
    """Tests for JobService status updates."""

    @pytest.fixture
    def job_service(self) -> JobService:
        """Create a fresh JobService instance."""
        return JobService(job_ttl_hours=24)

    def test_update_status(self, job_service: JobService) -> None:
        """Test updating job status."""
        job = job_service.create_job(url="https://youtube.com/watch?v=abc")

        updated = job_service.update_status(job.job_id, JobStatus.PROCESSING)

        assert updated.status == JobStatus.PROCESSING
        assert updated.started_at is not None

    def test_update_status_sets_completed_at(self, job_service: JobService) -> None:
        """Test that completing a job sets completed_at."""
        job = job_service.create_job(url="https://youtube.com/watch?v=abc")
        job_service.update_status(job.job_id, JobStatus.PROCESSING)

        updated = job_service.update_status(job.job_id, JobStatus.COMPLETED)

        assert updated.completed_at is not None

    def test_update_status_with_extra_fields(self, job_service: JobService) -> None:
        """Test updating status with additional fields."""
        job = job_service.create_job(url="https://youtube.com/watch?v=abc")

        updated = job_service.update_status(
            job.job_id,
            JobStatus.FAILED,
            error_message="Download failed",
        )

        assert updated.status == JobStatus.FAILED
        assert updated.error_message == "Download failed"

    def test_update_progress(self, job_service: JobService) -> None:
        """Test updating job progress."""
        job = job_service.create_job(url="https://youtube.com/watch?v=abc")

        updated = job_service.update_progress(job.job_id, 50)

        assert updated.progress == 50

    def test_update_progress_clamped(self, job_service: JobService) -> None:
        """Test that progress is clamped between 0 and 100."""
        job = job_service.create_job(url="https://youtube.com/watch?v=abc")

        # Clamp to 100
        updated = job_service.update_progress(job.job_id, 150)
        assert updated.progress == 100

        # Clamp to 0
        updated = job_service.update_progress(job.job_id, -10)
        assert updated.progress == 0

    def test_start_processing(self, job_service: JobService) -> None:
        """Test start_processing helper method."""
        job = job_service.create_job(url="https://youtube.com/watch?v=abc")

        updated = job_service.start_processing(job.job_id)

        assert updated.status == JobStatus.PROCESSING
        assert updated.started_at is not None

    def test_start_retry(self, job_service: JobService) -> None:
        """Test start_retry helper method."""
        job = job_service.create_job(url="https://youtube.com/watch?v=abc")

        updated = job_service.start_retry(job.job_id)

        assert updated.status == JobStatus.RETRYING
        assert updated.retry_count == 1

    def test_complete_job(self, job_service: JobService) -> None:
        """Test complete_job helper method."""
        job = job_service.create_job(url="https://youtube.com/watch?v=abc")
        job_service.start_processing(job.job_id)

        updated = job_service.complete_job(
            job.job_id,
            file_path="/downloads/video.mp4",
            file_size=1024000,
            duration=45.2,
        )

        assert updated.status == JobStatus.COMPLETED
        assert updated.progress == 100
        assert updated.file_path == "/downloads/video.mp4"
        assert updated.file_size == 1024000
        assert updated.duration == 45.2

    def test_fail_job(self, job_service: JobService) -> None:
        """Test fail_job helper method."""
        job = job_service.create_job(url="https://youtube.com/watch?v=abc")

        updated = job_service.fail_job(job.job_id, "Network error")

        assert updated.status == JobStatus.FAILED
        assert updated.error_message == "Network error"

    def test_set_queue_position(self, job_service: JobService) -> None:
        """Test set_queue_position method."""
        job = job_service.create_job(url="https://youtube.com/watch?v=abc")

        updated = job_service.set_queue_position(job.job_id, 5)

        assert updated.queue_position == 5


class TestJobServiceListing:
    """Tests for JobService job listing."""

    @pytest.fixture
    def job_service(self) -> JobService:
        """Create a fresh JobService instance with some jobs."""
        service = JobService(job_ttl_hours=24)

        # Create jobs with different statuses
        job1 = service.create_job(url="https://youtube.com/watch?v=a")
        job2 = service.create_job(url="https://youtube.com/watch?v=b")
        service.create_job(url="https://youtube.com/watch?v=c")  # stays PENDING

        service.start_processing(job1.job_id)
        service.complete_job(job2.job_id, "/path", 1000, 10.0)

        return service

    def test_list_jobs(self, job_service: JobService) -> None:
        """Test listing all jobs."""
        jobs = job_service.list_jobs()

        assert len(jobs) == 3

    def test_list_jobs_by_status(self, job_service: JobService) -> None:
        """Test listing jobs filtered by status."""
        pending = job_service.list_jobs(status=JobStatus.PENDING)
        assert len(pending) == 1

        completed = job_service.list_jobs(status=JobStatus.COMPLETED)
        assert len(completed) == 1

        processing = job_service.list_jobs(status=JobStatus.PROCESSING)
        assert len(processing) == 1

    def test_list_jobs_with_limit(self, job_service: JobService) -> None:
        """Test listing jobs with limit."""
        jobs = job_service.list_jobs(limit=2)

        assert len(jobs) == 2

    def test_get_pending_jobs(self, job_service: JobService) -> None:
        """Test get_pending_jobs helper method."""
        pending = job_service.get_pending_jobs()

        assert len(pending) == 1
        assert pending[0].status == JobStatus.PENDING

    def test_get_active_job_count(self, job_service: JobService) -> None:
        """Test get_active_job_count method."""
        # 1 PROCESSING + 1 PENDING = 2 active
        assert job_service.get_active_job_count() == 2


class TestJobServiceCleanup:
    """Tests for JobService TTL cleanup."""

    def test_cleanup_expired_jobs(self) -> None:
        """Test cleaning up expired jobs."""
        service = JobService(job_ttl_hours=24)

        # Create a job
        job = service.create_job(url="https://youtube.com/watch?v=abc")
        service.complete_job(job.job_id, "/path", 1000, 10.0)

        # Mock the created_at to be 25 hours ago
        job.created_at = datetime.now() - timedelta(hours=25)

        # Run cleanup
        count = service.cleanup_expired_jobs()

        assert count == 1
        assert service.get_job(job.job_id) is None

    def test_cleanup_preserves_active_jobs(self) -> None:
        """Test that cleanup preserves active jobs."""
        service = JobService(job_ttl_hours=24)

        # Create a job that stays PENDING
        job = service.create_job(url="https://youtube.com/watch?v=abc")

        # Mock the created_at to be 25 hours ago
        job.created_at = datetime.now() - timedelta(hours=25)

        # Run cleanup
        count = service.cleanup_expired_jobs()

        # Job should be preserved because it's PENDING (not terminal)
        assert count == 0
        assert service.get_job(job.job_id) is not None

    def test_cleanup_preserves_recent_jobs(self) -> None:
        """Test that cleanup preserves recent completed jobs."""
        service = JobService(job_ttl_hours=24)

        # Create and complete a recent job
        job = service.create_job(url="https://youtube.com/watch?v=abc")
        service.complete_job(job.job_id, "/path", 1000, 10.0)

        # Run cleanup
        count = service.cleanup_expired_jobs()

        # Job should be preserved because it's recent
        assert count == 0
        assert service.get_job(job.job_id) is not None


class TestJobServiceGlobalInstance:
    """Tests for global job service instance."""

    def test_configure_and_get_job_service(self) -> None:
        """Test configuring and retrieving global job service."""
        service = configure_job_service(job_ttl_hours=12)

        retrieved = get_job_service()

        assert retrieved is service
        assert retrieved.job_ttl_hours == 12

    def test_get_job_service_not_configured(self) -> None:
        """Test error when job service is not configured."""
        # Reset global instance
        import app.services.job_service as module

        module._job_service = None

        with pytest.raises(RuntimeError, match="Job service not configured"):
            get_job_service()

        # Restore for other tests
        configure_job_service()
