"""Unit tests for storage management."""

import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import StorageConfig
from app.services.storage import (
    CleanupResult,
    DiskUsage,
    StorageError,
    StorageManager,
    cleanup_scheduler,
    configure_storage,
    get_storage_manager,
)


class TestStorageConfig:
    """Test storage configuration fixture."""

    @pytest.fixture
    def storage_config(self, tmp_path: Path) -> StorageConfig:
        """Create a storage config with temporary directory."""
        return StorageConfig(
            output_dir=str(tmp_path / "downloads"),
            cookie_dir=str(tmp_path / "cookies"),
            cleanup_age=24,
            cleanup_threshold=80,
            max_file_size=524288000,  # 500MB
        )

    @pytest.fixture
    def storage_manager(self, storage_config: StorageConfig) -> StorageManager:
        """Create a storage manager instance."""
        manager = StorageManager(storage_config)
        manager.initialize()
        return manager


class TestStorageManagerInitialization(TestStorageConfig):
    """Tests for StorageManager initialization."""

    def test_initialize_creates_directory(self, storage_config: StorageConfig) -> None:
        """Test that initialize creates the output directory."""
        manager = StorageManager(storage_config)
        output_dir = Path(storage_config.output_dir)

        assert not output_dir.exists()
        manager.initialize()
        assert output_dir.exists()
        assert output_dir.is_dir()

    def test_initialize_existing_directory(self, storage_manager: StorageManager) -> None:
        """Test initialization with existing directory succeeds."""
        # Re-initialize should not raise
        storage_manager.initialize()
        assert storage_manager.output_dir.exists()

    def test_initialize_verifies_write_permission(self, storage_config: StorageConfig) -> None:
        """Test that initialize verifies write permissions."""
        manager = StorageManager(storage_config)
        manager.initialize()

        # If we got here, permissions were verified successfully
        assert manager.output_dir.exists()

    def test_initialize_permission_error(
        self, storage_config: StorageConfig, tmp_path: Path
    ) -> None:
        """Test that initialize raises error on permission failure."""
        manager = StorageManager(storage_config)
        manager.initialize()

        # Mock permission error on test file creation
        with (
            patch.object(Path, "touch", side_effect=PermissionError("Access denied")),
            pytest.raises(StorageError, match="Insufficient permissions"),
        ):
            # Create new manager to test initialization
            new_manager = StorageManager(storage_config)
            new_manager.initialize()

    def test_initialize_os_error(self, storage_config: StorageConfig) -> None:
        """Test that initialize raises StorageError on OSError."""
        manager = StorageManager(storage_config)

        with (
            patch.object(Path, "mkdir", side_effect=OSError("Disk error")),
            pytest.raises(StorageError, match="Failed to initialize"),
        ):
            manager.initialize()

    def test_config_values_stored(self, storage_config: StorageConfig) -> None:
        """Test that configuration values are properly stored."""
        manager = StorageManager(storage_config)

        assert manager.output_dir == Path(storage_config.output_dir)
        assert manager.cleanup_age_hours == storage_config.cleanup_age
        assert manager.cleanup_threshold == storage_config.cleanup_threshold
        assert manager.max_file_size == storage_config.max_file_size


class TestDiskUsageMonitoring(TestStorageConfig):
    """Tests for disk usage monitoring."""

    def test_get_disk_usage_returns_usage(self, storage_manager: StorageManager) -> None:
        """Test that get_disk_usage returns valid DiskUsage."""
        usage = storage_manager.get_disk_usage()

        assert isinstance(usage, DiskUsage)
        assert usage.total > 0
        assert usage.used >= 0
        assert usage.available >= 0
        assert 0 <= usage.percent_used <= 100

    def test_get_disk_usage_percent_calculation(self, storage_manager: StorageManager) -> None:
        """Test disk usage percentage is calculated correctly."""
        with patch("shutil.disk_usage") as mock_usage:
            mock_usage.return_value = MagicMock(total=1000, used=250, free=750)

            usage = storage_manager.get_disk_usage()

            assert usage.total == 1000
            assert usage.used == 250
            assert usage.available == 750
            assert usage.percent_used == 25.0

    def test_get_disk_usage_zero_total(self, storage_manager: StorageManager) -> None:
        """Test disk usage handles zero total gracefully."""
        with patch("shutil.disk_usage") as mock_usage:
            mock_usage.return_value = MagicMock(total=0, used=0, free=0)

            usage = storage_manager.get_disk_usage()

            assert usage.percent_used == 0.0

    def test_get_disk_usage_os_error(self, storage_manager: StorageManager) -> None:
        """Test that get_disk_usage raises StorageError on failure."""
        with (
            patch("shutil.disk_usage", side_effect=OSError("I/O error")),
            pytest.raises(StorageError, match="Failed to get disk usage"),
        ):
            storage_manager.get_disk_usage()

    def test_should_cleanup_below_threshold(self, storage_manager: StorageManager) -> None:
        """Test should_cleanup returns False below threshold."""
        with patch("shutil.disk_usage") as mock_usage:
            mock_usage.return_value = MagicMock(total=1000, used=500, free=500)

            assert storage_manager.should_cleanup() is False

    def test_should_cleanup_at_threshold(self, storage_manager: StorageManager) -> None:
        """Test should_cleanup returns True at threshold."""
        with patch("shutil.disk_usage") as mock_usage:
            mock_usage.return_value = MagicMock(total=1000, used=800, free=200)

            assert storage_manager.should_cleanup() is True

    def test_should_cleanup_above_threshold(self, storage_manager: StorageManager) -> None:
        """Test should_cleanup returns True above threshold."""
        with patch("shutil.disk_usage") as mock_usage:
            mock_usage.return_value = MagicMock(total=1000, used=900, free=100)

            assert storage_manager.should_cleanup() is True

    def test_should_cleanup_error_returns_false(self, storage_manager: StorageManager) -> None:
        """Test should_cleanup returns False on error."""
        with patch("shutil.disk_usage", side_effect=OSError("Error")):
            assert storage_manager.should_cleanup() is False


class TestFileSizeValidation(TestStorageConfig):
    """Tests for file size validation."""

    def test_validate_size_within_limit(self, storage_manager: StorageManager) -> None:
        """Test validation passes for sizes within limit."""
        assert storage_manager.validate_file_size(100 * 1024 * 1024) is True  # 100MB

    def test_validate_size_at_limit(self, storage_manager: StorageManager) -> None:
        """Test validation passes at exact limit."""
        assert storage_manager.validate_file_size(500 * 1024 * 1024) is True  # 500MB

    def test_validate_size_exceeds_limit(self, storage_manager: StorageManager) -> None:
        """Test validation fails for sizes exceeding limit."""
        assert storage_manager.validate_file_size(600 * 1024 * 1024) is False  # 600MB

    def test_validate_size_zero(self, storage_manager: StorageManager) -> None:
        """Test validation passes for zero size (unknown)."""
        assert storage_manager.validate_file_size(0) is True

    def test_validate_size_negative(self, storage_manager: StorageManager) -> None:
        """Test validation passes for negative size (unknown)."""
        assert storage_manager.validate_file_size(-1) is True

    def test_validate_size_custom_limit(self, tmp_path: Path) -> None:
        """Test validation with custom limit."""
        config = StorageConfig(
            output_dir=str(tmp_path / "downloads"),
            cookie_dir=str(tmp_path / "cookies"),
            max_file_size=1024 * 1024,  # 1MB
        )
        manager = StorageManager(config)
        manager.initialize()

        assert manager.validate_file_size(512 * 1024) is True  # 512KB
        assert manager.validate_file_size(2 * 1024 * 1024) is False  # 2MB


class TestActiveJobTracking(TestStorageConfig):
    """Tests for active job file tracking."""

    def test_register_active_job(self, storage_manager: StorageManager) -> None:
        """Test registering a file to an active job."""
        filepath = storage_manager.output_dir / "test_video.mp4"

        storage_manager.register_active_job("job-123", filepath)

        assert storage_manager.is_file_active(filepath) is True
        assert storage_manager.get_active_job_count() == 1

    def test_register_multiple_files_same_job(self, storage_manager: StorageManager) -> None:
        """Test registering multiple files to the same job."""
        file1 = storage_manager.output_dir / "video.mp4"
        file2 = storage_manager.output_dir / "video.srt"

        storage_manager.register_active_job("job-123", file1)
        storage_manager.register_active_job("job-123", file2)

        assert storage_manager.is_file_active(file1) is True
        assert storage_manager.is_file_active(file2) is True
        assert storage_manager.get_active_job_count() == 1

    def test_register_files_different_jobs(self, storage_manager: StorageManager) -> None:
        """Test registering files to different jobs."""
        file1 = storage_manager.output_dir / "video1.mp4"
        file2 = storage_manager.output_dir / "video2.mp4"

        storage_manager.register_active_job("job-1", file1)
        storage_manager.register_active_job("job-2", file2)

        assert storage_manager.get_active_job_count() == 2

    def test_unregister_active_job(self, storage_manager: StorageManager) -> None:
        """Test unregistering releases files."""
        filepath = storage_manager.output_dir / "test_video.mp4"

        storage_manager.register_active_job("job-123", filepath)
        assert storage_manager.is_file_active(filepath) is True

        storage_manager.unregister_active_job("job-123")
        assert storage_manager.is_file_active(filepath) is False
        assert storage_manager.get_active_job_count() == 0

    def test_unregister_nonexistent_job(self, storage_manager: StorageManager) -> None:
        """Test unregistering non-existent job doesn't raise."""
        storage_manager.unregister_active_job("nonexistent")
        assert storage_manager.get_active_job_count() == 0

    def test_is_file_active_unregistered(self, storage_manager: StorageManager) -> None:
        """Test is_file_active returns False for unregistered files."""
        filepath = storage_manager.output_dir / "unregistered.mp4"
        assert storage_manager.is_file_active(filepath) is False

    def test_file_active_uses_absolute_path(self, storage_manager: StorageManager) -> None:
        """Test that file tracking uses absolute paths."""
        abs_path = storage_manager.output_dir / "test.mp4"

        storage_manager.register_active_job("job-123", abs_path)

        # Check with resolved path
        assert storage_manager.is_file_active(abs_path.resolve()) is True


class TestCleanupOldFiles(TestStorageConfig):
    """Tests for cleanup_old_files functionality."""

    def test_cleanup_deletes_old_files(self, storage_manager: StorageManager) -> None:
        """Test that old files are deleted."""
        # Create an old file (older than 24 hours)
        old_file = storage_manager.output_dir / "old_video.mp4"
        old_file.touch()

        # Set mtime to 25 hours ago
        old_time = time.time() - (25 * 3600)
        os.utime(old_file, (old_time, old_time))

        result = storage_manager.cleanup_old_files()

        assert result.files_deleted == 1
        assert not old_file.exists()
        assert result.dry_run is False

    def test_cleanup_preserves_new_files(self, storage_manager: StorageManager) -> None:
        """Test that new files are preserved."""
        # Create a new file
        new_file = storage_manager.output_dir / "new_video.mp4"
        new_file.touch()

        result = storage_manager.cleanup_old_files()

        assert result.files_deleted == 0
        assert new_file.exists()

    def test_cleanup_preserves_active_job_files(self, storage_manager: StorageManager) -> None:
        """Test that files belonging to active jobs are preserved."""
        # Create an old file
        old_file = storage_manager.output_dir / "active_download.mp4"
        old_file.touch()
        old_time = time.time() - (25 * 3600)
        os.utime(old_file, (old_time, old_time))

        # Register as active
        storage_manager.register_active_job("job-123", old_file)

        result = storage_manager.cleanup_old_files()

        assert result.files_deleted == 0
        assert result.files_preserved == 1
        assert old_file.exists()

    def test_cleanup_skips_directories(self, storage_manager: StorageManager) -> None:
        """Test that directories are skipped during cleanup."""
        # Create a subdirectory
        subdir = storage_manager.output_dir / "subdir"
        subdir.mkdir()

        result = storage_manager.cleanup_old_files()

        assert subdir.exists()
        assert result.files_deleted == 0

    def test_cleanup_skips_hidden_files(self, storage_manager: StorageManager) -> None:
        """Test that hidden files are skipped during cleanup."""
        # Create an old hidden file
        hidden_file = storage_manager.output_dir / ".hidden_file"
        hidden_file.touch()
        old_time = time.time() - (25 * 3600)
        os.utime(hidden_file, (old_time, old_time))

        result = storage_manager.cleanup_old_files()

        assert result.files_deleted == 0
        assert hidden_file.exists()

    def test_cleanup_reports_bytes_reclaimed(self, storage_manager: StorageManager) -> None:
        """Test that cleanup reports bytes reclaimed."""
        # Create file with known size
        old_file = storage_manager.output_dir / "sized_file.mp4"
        old_file.write_bytes(b"x" * 1024)  # 1KB

        old_time = time.time() - (25 * 3600)
        os.utime(old_file, (old_time, old_time))

        result = storage_manager.cleanup_old_files()

        assert result.files_deleted == 1
        assert result.bytes_reclaimed == 1024

    def test_cleanup_multiple_files(self, storage_manager: StorageManager) -> None:
        """Test cleanup of multiple old files."""
        old_time = time.time() - (25 * 3600)

        # Create multiple old files
        for i in range(5):
            f = storage_manager.output_dir / f"old_file_{i}.mp4"
            f.write_bytes(b"x" * 100)
            os.utime(f, (old_time, old_time))

        result = storage_manager.cleanup_old_files()

        assert result.files_deleted == 5
        assert result.bytes_reclaimed == 500


class TestCleanupDryRun(TestStorageConfig):
    """Tests for dry-run cleanup mode."""

    def test_dry_run_does_not_delete(self, storage_manager: StorageManager) -> None:
        """Test that dry-run doesn't actually delete files."""
        old_file = storage_manager.output_dir / "old_video.mp4"
        old_file.write_bytes(b"content")
        old_time = time.time() - (25 * 3600)
        os.utime(old_file, (old_time, old_time))

        result = storage_manager.cleanup_old_files(dry_run=True)

        assert result.files_deleted == 1
        assert result.dry_run is True
        assert old_file.exists()  # File still exists

    def test_dry_run_reports_what_would_delete(self, storage_manager: StorageManager) -> None:
        """Test that dry-run reports correct statistics."""
        old_time = time.time() - (25 * 3600)

        # Create multiple files
        for i in range(3):
            f = storage_manager.output_dir / f"file_{i}.mp4"
            f.write_bytes(b"x" * 100)
            os.utime(f, (old_time, old_time))

        # Create active file
        active_file = storage_manager.output_dir / "active.mp4"
        active_file.touch()
        os.utime(active_file, (old_time, old_time))
        storage_manager.register_active_job("job-1", active_file)

        result = storage_manager.cleanup_old_files(dry_run=True)

        assert result.files_deleted == 3
        assert result.files_preserved == 1
        assert result.bytes_reclaimed == 300
        assert result.dry_run is True

        # All files still exist
        for i in range(3):
            assert (storage_manager.output_dir / f"file_{i}.mp4").exists()
        assert active_file.exists()


class TestGetOutputPath(TestStorageConfig):
    """Tests for get_output_path helper."""

    def test_get_output_path(self, storage_manager: StorageManager) -> None:
        """Test get_output_path returns correct path."""
        path = storage_manager.get_output_path("video.mp4")

        assert path == storage_manager.output_dir / "video.mp4"

    def test_get_output_path_with_subdirectory(self, storage_manager: StorageManager) -> None:
        """Test get_output_path with subdirectory in filename."""
        path = storage_manager.get_output_path("subdir/video.mp4")

        assert path == storage_manager.output_dir / "subdir" / "video.mp4"


class TestCleanupScheduler(TestStorageConfig):
    """Tests for the cleanup scheduler."""

    @pytest.mark.asyncio
    async def test_scheduler_runs_cleanup(self, storage_manager: StorageManager) -> None:
        """Test scheduler triggers cleanup when threshold exceeded."""
        # Create old file
        old_file = storage_manager.output_dir / "old.mp4"
        old_file.touch()
        old_time = time.time() - (25 * 3600)
        os.utime(old_file, (old_time, old_time))

        with patch("shutil.disk_usage") as mock_usage:
            # Set disk usage above threshold
            mock_usage.return_value = MagicMock(total=1000, used=900, free=100)

            # Run scheduler once with very short interval
            result = await cleanup_scheduler(storage_manager, interval=0.01, run_once=True)

            assert result is not None
            assert result.files_deleted == 1

    @pytest.mark.asyncio
    async def test_scheduler_skips_below_threshold(self, storage_manager: StorageManager) -> None:
        """Test scheduler skips cleanup when below threshold."""
        with patch("shutil.disk_usage") as mock_usage:
            # Set disk usage below threshold
            mock_usage.return_value = MagicMock(total=1000, used=500, free=500)

            result = await cleanup_scheduler(storage_manager, interval=0.01, run_once=True)

            assert result is None


class TestGlobalFunctions(TestStorageConfig):
    """Tests for global storage manager functions."""

    def test_configure_storage(self, storage_config: StorageConfig) -> None:
        """Test configure_storage creates and initializes manager."""
        manager = configure_storage(storage_config)

        assert manager is not None
        assert manager.output_dir.exists()

    def test_get_storage_manager_after_configure(self, storage_config: StorageConfig) -> None:
        """Test get_storage_manager returns configured manager."""
        expected = configure_storage(storage_config)
        actual = get_storage_manager()

        assert actual is expected

    def test_get_storage_manager_not_configured(self) -> None:
        """Test get_storage_manager raises when not configured."""
        # Reset global state
        import app.services.storage as storage_module

        storage_module._storage_manager = None

        with pytest.raises(RuntimeError, match="not configured"):
            get_storage_manager()


class TestCleanupResultDataclass:
    """Tests for CleanupResult dataclass."""

    def test_cleanup_result_creation(self) -> None:
        """Test CleanupResult can be created with all fields."""
        result = CleanupResult(
            files_deleted=5,
            bytes_reclaimed=1024000,
            files_preserved=2,
            dry_run=False,
        )

        assert result.files_deleted == 5
        assert result.bytes_reclaimed == 1024000
        assert result.files_preserved == 2
        assert result.dry_run is False


class TestDiskUsageDataclass:
    """Tests for DiskUsage dataclass."""

    def test_disk_usage_creation(self) -> None:
        """Test DiskUsage can be created with all fields."""
        usage = DiskUsage(
            total=1000000000,
            used=500000000,
            available=500000000,
            percent_used=50.0,
        )

        assert usage.total == 1000000000
        assert usage.used == 500000000
        assert usage.available == 500000000
        assert usage.percent_used == 50.0
