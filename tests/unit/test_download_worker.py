"""Tests for the download worker (job processing, retries, lifecycle).

Covers requirements 14, 15, 26 (job lifecycle, retry handling,
concurrency slot release) at the worker level.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.services.download_worker as worker_module
from app.models.video import DownloadResult
from app.providers.exceptions import DownloadError, ProviderError
from app.services.download_worker import (
    DownloadWorker,
    configure_download_worker,
    get_download_worker,
    start_download_worker,
    stop_download_worker,
)


@pytest.fixture
def mock_job():
    """A job mock with retry state and download params."""
    job = MagicMock()
    job.url = "https://youtube.com/watch?v=test"
    job.retry_count = 0
    job.max_retries = 3
    job.can_retry.return_value = True
    job.params = {
        "format_id": "22",
        "output_template": None,
        "extract_audio": False,
        "audio_format": None,
        "include_subtitles": False,
        "subtitle_lang": None,
    }
    return job


@pytest.fixture
def services(mock_job):
    """Mocked job service, queue, storage and provider manager."""
    job_service = MagicMock()
    job_service.get_job.return_value = mock_job

    download_queue = MagicMock()
    download_queue.dequeue = AsyncMock(return_value=None)
    download_queue.enqueue = AsyncMock()
    download_queue.release_slot = AsyncMock()

    storage_manager = MagicMock()

    provider = MagicMock()
    provider.download = AsyncMock(
        return_value=DownloadResult(
            file_path="/downloads/video.mp4",
            file_size=1024,
            duration=12.5,
            format_id="22",
        )
    )

    provider_manager = MagicMock()
    provider_manager.get_provider_for_url.return_value = provider

    return {
        "job_service": job_service,
        "download_queue": download_queue,
        "storage_manager": storage_manager,
        "provider": provider,
        "provider_manager": provider_manager,
    }


@pytest.fixture
def worker(services):
    """Worker wired to the mocked services."""
    return DownloadWorker(
        provider_manager=services["provider_manager"],
        job_service=services["job_service"],
        download_queue=services["download_queue"],
        storage_manager=services["storage_manager"],
        poll_interval=0.01,
    )


class TestWorkerLifecycle:
    """start/stop semantics and the polling loop."""

    @pytest.mark.asyncio
    async def test_start_and_stop(self, worker):
        """Worker starts a background task and stops it cleanly."""
        await worker.start()
        assert worker._running is True

        await worker.stop()
        assert worker._running is False
        assert worker._worker_task is None

    @pytest.mark.asyncio
    async def test_start_twice_is_noop(self, worker):
        """A second start on a running worker does not spawn a new task."""
        await worker.start()
        first_task = worker._worker_task

        await worker.start()

        assert worker._worker_task is first_task
        await worker.stop()

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, worker):
        """Stopping a non-running worker is a no-op."""
        await worker.stop()
        assert worker._running is False

    @pytest.mark.asyncio
    async def test_loop_survives_dequeue_errors(self, worker, services):
        """Exceptions in the polling loop are logged, not fatal."""
        services["download_queue"].dequeue.side_effect = RuntimeError("queue exploded")

        await worker.start()
        await asyncio.sleep(0.05)
        await worker.stop()

        assert services["download_queue"].dequeue.call_count >= 1

    @pytest.mark.asyncio
    async def test_loop_processes_dequeued_job(self, worker, services):
        """A dequeued job id triggers processing."""
        services["download_queue"].dequeue.side_effect = ["job-1", None, None]

        with patch.object(worker, "_process_job", new_callable=AsyncMock) as process:
            await worker.start()
            await asyncio.sleep(0.05)
            await worker.stop()

        process.assert_called_once_with("job-1")


class TestProcessJob:
    """_process_job outcome paths."""

    @pytest.mark.asyncio
    async def test_success_completes_job_and_releases_slot(self, worker, services, mock_job):
        """Happy path: registers file, completes job, releases the slot."""
        await worker.process_single_job("job-1")

        services["job_service"].start_processing.assert_called_once_with("job-1")
        services["storage_manager"].register_active_job.assert_called_once()
        services["job_service"].complete_job.assert_called_once_with(
            job_id="job-1",
            file_path="/downloads/video.mp4",
            file_size=1024,
            duration=12.5,
        )
        services["download_queue"].release_slot.assert_awaited_once_with("job-1")

    @pytest.mark.asyncio
    async def test_job_not_found_releases_slot(self, worker, services):
        """Missing job releases the slot without processing."""
        services["job_service"].get_job.return_value = None

        await worker.process_single_job("ghost")

        services["job_service"].start_processing.assert_not_called()
        services["download_queue"].release_slot.assert_awaited_once_with("ghost")

    @pytest.mark.asyncio
    async def test_job_vanishing_mid_flight_fails_job(self, worker, services, mock_job):
        """Job disappearing between dequeue and download fails cleanly."""
        services["job_service"].get_job.side_effect = [mock_job, None]

        await worker.process_single_job("job-1")

        services["job_service"].fail_job.assert_called_once()
        assert "not found" in services["job_service"].fail_job.call_args[0][1].lower()
        services["download_queue"].release_slot.assert_awaited_once_with("job-1")

    @pytest.mark.asyncio
    async def test_provider_error_fails_job(self, worker, services):
        """Non-retriable provider errors fail the job immediately."""
        services["provider"].download.side_effect = ProviderError("cookies expired")

        await worker.process_single_job("job-1")

        services["job_service"].fail_job.assert_called_once_with("job-1", "cookies expired")
        services["download_queue"].release_slot.assert_awaited_once_with("job-1")

    @pytest.mark.asyncio
    async def test_unexpected_error_fails_job(self, worker, services):
        """Unexpected exceptions fail the job with context."""
        services["provider"].download.side_effect = RuntimeError("disk on fire")

        await worker.process_single_job("job-1")

        services["job_service"].fail_job.assert_called_once()
        message = services["job_service"].fail_job.call_args[0][1]
        assert "Unexpected error" in message
        assert "disk on fire" in message

    @pytest.mark.asyncio
    async def test_metrics_recorded_on_success(self, worker, services):
        """Download metrics are recorded with success status."""
        with patch.object(worker_module.MetricsCollector, "record_download") as record:
            await worker.process_single_job("job-1")

        record.assert_called_once()
        assert record.call_args.kwargs["status"] == "success"
        assert record.call_args.kwargs["size"] == 1024

    @pytest.mark.asyncio
    async def test_metrics_recorded_on_failure(self, worker, services):
        """Download metrics are recorded with failed status."""
        services["provider"].download.side_effect = ProviderError("boom")

        with patch.object(worker_module.MetricsCollector, "record_download") as record:
            await worker.process_single_job("job-1")

        assert record.call_args.kwargs["status"] == "failed"


class TestRetryHandling:
    """Retry semantics on DownloadError."""

    @pytest.mark.asyncio
    async def test_retriable_error_requeues_job(self, worker, services, mock_job):
        """A retriable failure marks the job RETRYING and re-enqueues it."""
        services["provider"].download.side_effect = DownloadError("network reset")
        mock_job.can_retry.return_value = True

        await worker.process_single_job("job-1")

        services["job_service"].start_retry.assert_called_once_with("job-1")
        services["download_queue"].enqueue.assert_awaited_once_with("job-1")
        services["job_service"].fail_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_retry_with_full_queue_fails_job(self, worker, services, mock_job):
        """If re-enqueue hits a full queue, the job fails instead of hanging."""
        services["provider"].download.side_effect = DownloadError("network reset")
        mock_job.can_retry.return_value = True
        services["download_queue"].enqueue.side_effect = ValueError("Queue is full")

        await worker.process_single_job("job-1")

        services["job_service"].fail_job.assert_called_once()
        message = services["job_service"].fail_job.call_args[0][1]
        assert "queue full" in message.lower()

    @pytest.mark.asyncio
    async def test_max_retries_exceeded_fails_job(self, worker, services, mock_job):
        """When retries are exhausted the job fails with a clear message."""
        services["provider"].download.side_effect = DownloadError("network reset")
        mock_job.can_retry.return_value = False

        await worker.process_single_job("job-1")

        services["job_service"].fail_job.assert_called_once()
        message = services["job_service"].fail_job.call_args[0][1]
        assert "Max retries" in message
        services["download_queue"].enqueue.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_retry_with_vanished_job_is_noop(self, worker, services, mock_job):
        """A download error for a vanished job does not crash the handler."""
        services["provider"].download.side_effect = DownloadError("network reset")
        services["job_service"].get_job.side_effect = [mock_job, mock_job, None]

        await worker.process_single_job("job-1")

        services["job_service"].start_retry.assert_not_called()
        services["job_service"].fail_job.assert_not_called()


class TestGlobalWorker:
    """Global configure/get/start/stop helpers."""

    @pytest.fixture(autouse=True)
    def reset_global(self):
        """Save and restore the module-level worker instance."""
        saved = worker_module._download_worker
        worker_module._download_worker = None
        yield
        worker_module._download_worker = saved

    def test_get_unconfigured_raises(self):
        """Calling get_download_worker without configure raises RuntimeError."""
        with pytest.raises(RuntimeError, match="not configured"):
            get_download_worker()

    @pytest.mark.asyncio
    async def test_configure_start_stop_roundtrip(self, services):
        """Roundtrip: configure + global start/stop drive the same instance."""
        worker = configure_download_worker(
            provider_manager=services["provider_manager"],
            job_service=services["job_service"],
            download_queue=services["download_queue"],
            storage_manager=services["storage_manager"],
            poll_interval=0.01,
        )

        assert get_download_worker() is worker

        await start_download_worker()
        assert worker._running is True

        await stop_download_worker()
        assert worker._running is False
