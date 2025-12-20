"""Tests for download queue."""

import pytest

from app.services.download_queue import (
    PRIORITY_DOWNLOAD,
    PRIORITY_METADATA,
    DownloadQueue,
    QueuedJob,
    configure_download_queue,
    get_download_queue,
)


class TestQueuedJob:
    """Tests for QueuedJob dataclass."""

    def test_queued_job_ordering(self) -> None:
        """Test that QueuedJob orders by priority then enqueue_time."""
        job_low = QueuedJob(priority=10, enqueue_time=1.0, job_id="low")
        job_high = QueuedJob(priority=1, enqueue_time=2.0, job_id="high")
        job_low_earlier = QueuedJob(priority=10, enqueue_time=0.5, job_id="earlier")

        # Higher priority (lower number) comes first
        assert job_high < job_low

        # Same priority, earlier time comes first
        assert job_low_earlier < job_low


class TestDownloadQueueInitialization:
    """Tests for DownloadQueue initialization."""

    def test_queue_initialization(self) -> None:
        """Test creating a new download queue."""
        queue = DownloadQueue(max_concurrent=5, max_queue_size=100)

        assert queue.max_concurrent == 5
        assert queue.max_queue_size == 100
        assert queue.get_queue_size() == 0
        assert queue.get_active_count() == 0

    def test_queue_default_values(self) -> None:
        """Test queue uses default values."""
        queue = DownloadQueue()

        assert queue.max_concurrent == 5
        assert queue.max_queue_size == 100


class TestDownloadQueueEnqueue:
    """Tests for enqueue operations."""

    @pytest.fixture
    def queue(self) -> DownloadQueue:
        """Create a fresh download queue."""
        return DownloadQueue(max_concurrent=2, max_queue_size=5)

    @pytest.mark.asyncio
    async def test_enqueue_job(self, queue: DownloadQueue) -> None:
        """Test enqueueing a job."""
        position = await queue.enqueue("job-1", priority=PRIORITY_DOWNLOAD)

        assert position == 1
        assert queue.get_queue_size() == 1

    @pytest.mark.asyncio
    async def test_enqueue_multiple_jobs(self, queue: DownloadQueue) -> None:
        """Test enqueueing multiple jobs."""
        pos1 = await queue.enqueue("job-1")
        pos2 = await queue.enqueue("job-2")
        pos3 = await queue.enqueue("job-3")

        assert pos1 == 1
        assert pos2 == 2
        assert pos3 == 3
        assert queue.get_queue_size() == 3

    @pytest.mark.asyncio
    async def test_enqueue_with_priority(self, queue: DownloadQueue) -> None:
        """Test that high priority jobs get earlier position."""
        # Enqueue low priority first
        await queue.enqueue("job-low", priority=PRIORITY_DOWNLOAD)

        # Enqueue high priority second
        pos_high = await queue.enqueue("job-high", priority=PRIORITY_METADATA)

        # High priority should be position 1 (before low priority)
        assert pos_high == 1

    @pytest.mark.asyncio
    async def test_enqueue_duplicate_job(self, queue: DownloadQueue) -> None:
        """Test enqueueing the same job twice."""
        pos1 = await queue.enqueue("job-1")
        pos2 = await queue.enqueue("job-1")

        # Should return same position
        assert pos1 == pos2
        # Should only have one job in queue
        assert queue.get_queue_size() == 1

    @pytest.mark.asyncio
    async def test_enqueue_queue_full(self, queue: DownloadQueue) -> None:
        """Test enqueueing when queue is full."""
        # Fill the queue
        for i in range(5):
            await queue.enqueue(f"job-{i}")

        # Try to enqueue one more
        with pytest.raises(ValueError, match="Queue is full"):
            await queue.enqueue("job-overflow")


class TestDownloadQueueDequeue:
    """Tests for dequeue operations."""

    @pytest.fixture
    def queue(self) -> DownloadQueue:
        """Create a fresh download queue."""
        return DownloadQueue(max_concurrent=2, max_queue_size=10)

    @pytest.mark.asyncio
    async def test_dequeue_job(self, queue: DownloadQueue) -> None:
        """Test dequeuing a job."""
        await queue.enqueue("job-1")

        job_id = await queue.dequeue()

        assert job_id == "job-1"
        assert queue.get_queue_size() == 0
        assert queue.get_active_count() == 1

    @pytest.mark.asyncio
    async def test_dequeue_empty_queue(self, queue: DownloadQueue) -> None:
        """Test dequeuing from empty queue."""
        job_id = await queue.dequeue()

        assert job_id is None

    @pytest.mark.asyncio
    async def test_dequeue_priority_order(self, queue: DownloadQueue) -> None:
        """Test that jobs are dequeued in priority order."""
        await queue.enqueue("job-low", priority=PRIORITY_DOWNLOAD)
        await queue.enqueue("job-high", priority=PRIORITY_METADATA)

        # High priority should come out first
        first = await queue.dequeue()
        assert first == "job-high"

        second = await queue.dequeue()
        assert second == "job-low"

    @pytest.mark.asyncio
    async def test_dequeue_respects_concurrency(self, queue: DownloadQueue) -> None:
        """Test that dequeue respects max concurrent limit."""
        await queue.enqueue("job-1")
        await queue.enqueue("job-2")
        await queue.enqueue("job-3")

        # Dequeue 2 jobs (max concurrent)
        await queue.dequeue()
        await queue.dequeue()

        # Third dequeue should return None (no slots available)
        third = await queue.dequeue()
        assert third is None
        assert queue.get_active_count() == 2


class TestDownloadQueueReleaseSlot:
    """Tests for slot release operations."""

    @pytest.fixture
    def queue(self) -> DownloadQueue:
        """Create a fresh download queue."""
        return DownloadQueue(max_concurrent=2, max_queue_size=10)

    @pytest.mark.asyncio
    async def test_release_slot(self, queue: DownloadQueue) -> None:
        """Test releasing a download slot."""
        await queue.enqueue("job-1")
        job_id = await queue.dequeue()

        assert queue.get_active_count() == 1

        await queue.release_slot(job_id)

        assert queue.get_active_count() == 0

    @pytest.mark.asyncio
    async def test_release_slot_allows_more_dequeue(self, queue: DownloadQueue) -> None:
        """Test that releasing a slot allows more dequeues."""
        await queue.enqueue("job-1")
        await queue.enqueue("job-2")
        await queue.enqueue("job-3")

        # Fill concurrency limit
        await queue.dequeue()
        job2 = await queue.dequeue()

        # Can't dequeue more
        assert await queue.dequeue() is None

        # Release a slot
        await queue.release_slot(job2)

        # Now can dequeue
        job3 = await queue.dequeue()
        assert job3 == "job-3"


class TestDownloadQueueQueries:
    """Tests for queue query methods."""

    @pytest.fixture
    def queue(self) -> DownloadQueue:
        """Create a fresh download queue."""
        return DownloadQueue(max_concurrent=3, max_queue_size=10)

    @pytest.mark.asyncio
    async def test_get_queue_position(self, queue: DownloadQueue) -> None:
        """Test getting queue position."""
        await queue.enqueue("job-1")
        await queue.enqueue("job-2")

        assert queue.get_queue_position("job-1") == 1
        assert queue.get_queue_position("job-2") == 2

    @pytest.mark.asyncio
    async def test_get_queue_position_not_found(self, queue: DownloadQueue) -> None:
        """Test getting position for non-queued job."""
        position = queue.get_queue_position("non-existent")

        assert position is None

    @pytest.mark.asyncio
    async def test_is_active(self, queue: DownloadQueue) -> None:
        """Test checking if job is active."""
        await queue.enqueue("job-1")

        # Not active yet
        assert not queue.is_active("job-1")

        # Dequeue makes it active
        await queue.dequeue()
        assert queue.is_active("job-1")

    @pytest.mark.asyncio
    async def test_get_available_slots(self, queue: DownloadQueue) -> None:
        """Test getting available slots."""
        assert queue.get_available_slots() == 3

        await queue.enqueue("job-1")
        await queue.dequeue()

        assert queue.get_available_slots() == 2

    @pytest.mark.asyncio
    async def test_get_stats(self, queue: DownloadQueue) -> None:
        """Test getting queue statistics."""
        await queue.enqueue("job-1")
        await queue.enqueue("job-2")
        await queue.dequeue()

        stats = queue.get_stats()

        assert stats["queue_size"] == 1
        assert stats["active_count"] == 1
        assert stats["available_slots"] == 2
        assert stats["max_concurrent"] == 3


class TestDownloadQueueRemove:
    """Tests for job removal."""

    @pytest.fixture
    def queue(self) -> DownloadQueue:
        """Create a fresh download queue."""
        return DownloadQueue(max_concurrent=2, max_queue_size=10)

    @pytest.mark.asyncio
    async def test_remove_job(self, queue: DownloadQueue) -> None:
        """Test removing a queued job."""
        await queue.enqueue("job-1")
        await queue.enqueue("job-2")

        removed = await queue.remove_job("job-1")

        assert removed is True
        assert queue.get_queue_size() == 1
        assert queue.get_queue_position("job-1") is None

    @pytest.mark.asyncio
    async def test_remove_job_not_found(self, queue: DownloadQueue) -> None:
        """Test removing a non-existent job."""
        removed = await queue.remove_job("non-existent")

        assert removed is False

    @pytest.mark.asyncio
    async def test_remove_active_job(self, queue: DownloadQueue) -> None:
        """Test that active jobs cannot be removed."""
        await queue.enqueue("job-1")
        await queue.dequeue()  # Make it active

        removed = await queue.remove_job("job-1")

        assert removed is False
        assert queue.is_active("job-1")


class TestDownloadQueueGlobalInstance:
    """Tests for global download queue instance."""

    def test_configure_and_get_queue(self) -> None:
        """Test configuring and retrieving global queue."""
        queue = configure_download_queue(max_concurrent=10, max_queue_size=50)

        retrieved = get_download_queue()

        assert retrieved is queue
        assert retrieved.max_concurrent == 10
        assert retrieved.max_queue_size == 50

    def test_get_queue_not_configured(self) -> None:
        """Test error when queue is not configured."""
        # Reset global instance
        import app.services.download_queue as module

        module._download_queue = None

        with pytest.raises(RuntimeError, match="Download queue not configured"):
            get_download_queue()

        # Restore for other tests
        configure_download_queue()


class TestPriorityConstants:
    """Tests for priority constants."""

    def test_priority_values(self) -> None:
        """Test priority constants have correct ordering."""
        # Metadata should have higher priority (lower number)
        assert PRIORITY_METADATA < PRIORITY_DOWNLOAD

    def test_priority_values_specific(self) -> None:
        """Test specific priority values."""
        assert PRIORITY_METADATA == 1
        assert PRIORITY_DOWNLOAD == 10
