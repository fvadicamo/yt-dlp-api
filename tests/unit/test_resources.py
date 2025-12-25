"""Unit tests for resource monitoring and validation."""

from unittest.mock import MagicMock, patch

from app.core.resources import (
    ResourceCheckResult,
    ResourceRequirements,
    ResourceUsage,
    check_minimum_resources,
    get_current_usage,
)


class TestResourceUsage:
    """Tests for ResourceUsage dataclass."""

    def test_resource_usage_creation(self) -> None:
        """Test creating ResourceUsage with valid values."""
        usage = ResourceUsage(
            cpu_percent=50.0,
            memory_total_gb=16.0,
            memory_available_gb=8.0,
            memory_percent=50.0,
            disk_total_gb=500.0,
            disk_available_gb=250.0,
            disk_percent=50.0,
        )

        assert usage.cpu_percent == 50.0
        assert usage.memory_total_gb == 16.0
        assert usage.memory_available_gb == 8.0
        assert usage.memory_percent == 50.0
        assert usage.disk_total_gb == 500.0
        assert usage.disk_available_gb == 250.0
        assert usage.disk_percent == 50.0


class TestResourceRequirements:
    """Tests for ResourceRequirements dataclass."""

    def test_default_requirements(self) -> None:
        """Test default resource requirements."""
        req = ResourceRequirements()

        assert req.min_memory_gb == 1.0
        assert req.min_disk_gb == 10.0
        assert req.warn_memory_gb == 2.0
        assert req.warn_disk_gb == 20.0

    def test_custom_requirements(self) -> None:
        """Test custom resource requirements."""
        req = ResourceRequirements(
            min_memory_gb=2.0,
            min_disk_gb=50.0,
            warn_memory_gb=4.0,
            warn_disk_gb=100.0,
        )

        assert req.min_memory_gb == 2.0
        assert req.min_disk_gb == 50.0
        assert req.warn_memory_gb == 4.0
        assert req.warn_disk_gb == 100.0


class TestGetCurrentUsage:
    """Tests for get_current_usage function."""

    @patch("app.core.resources.psutil.cpu_percent")
    @patch("app.core.resources.psutil.virtual_memory")
    @patch("app.core.resources.psutil.disk_usage")
    def test_get_current_usage_success(
        self, mock_disk: MagicMock, mock_memory: MagicMock, mock_cpu: MagicMock
    ) -> None:
        """Test getting current resource usage."""
        mock_cpu.return_value = 25.0

        mock_memory.return_value = MagicMock(
            total=16 * 1024**3,  # 16 GB
            available=8 * 1024**3,  # 8 GB
            percent=50.0,
        )

        mock_disk.return_value = MagicMock(
            total=500 * 1024**3,  # 500 GB
            free=250 * 1024**3,  # 250 GB
            percent=50.0,
        )

        usage = get_current_usage("/tmp")

        assert usage.cpu_percent == 25.0
        assert usage.memory_total_gb == 16.0
        assert usage.memory_available_gb == 8.0
        assert usage.memory_percent == 50.0
        assert usage.disk_total_gb == 500.0
        assert usage.disk_available_gb == 250.0
        assert usage.disk_percent == 50.0

    @patch("app.core.resources.psutil.cpu_percent")
    @patch("app.core.resources.psutil.virtual_memory")
    @patch("app.core.resources.psutil.disk_usage")
    def test_get_current_usage_default_path(
        self, mock_disk: MagicMock, mock_memory: MagicMock, mock_cpu: MagicMock
    ) -> None:
        """Test getting usage with default path."""
        mock_cpu.return_value = 10.0
        mock_memory.return_value = MagicMock(total=8 * 1024**3, available=4 * 1024**3, percent=50.0)
        mock_disk.return_value = MagicMock(total=100 * 1024**3, free=50 * 1024**3, percent=50.0)

        usage = get_current_usage()

        # Should use root filesystem
        mock_disk.assert_called_once_with("/")
        assert usage is not None


class TestCheckMinimumResources:
    """Tests for check_minimum_resources function."""

    @patch("app.core.resources.get_current_usage")
    def test_check_resources_all_pass(self, mock_usage: MagicMock) -> None:
        """Test resource check when all requirements are met."""
        mock_usage.return_value = ResourceUsage(
            cpu_percent=25.0,
            memory_total_gb=16.0,
            memory_available_gb=8.0,
            memory_percent=50.0,
            disk_total_gb=500.0,
            disk_available_gb=250.0,
            disk_percent=50.0,
        )

        result = check_minimum_resources()

        assert result.passed is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    @patch("app.core.resources.get_current_usage")
    def test_check_resources_memory_error(self, mock_usage: MagicMock) -> None:
        """Test resource check with insufficient memory."""
        mock_usage.return_value = ResourceUsage(
            cpu_percent=25.0,
            memory_total_gb=2.0,
            memory_available_gb=0.5,  # Below 1 GB minimum
            memory_percent=75.0,
            disk_total_gb=500.0,
            disk_available_gb=250.0,
            disk_percent=50.0,
        )

        result = check_minimum_resources()

        assert result.passed is False
        assert len(result.errors) == 1
        assert "Insufficient memory" in result.errors[0]

    @patch("app.core.resources.get_current_usage")
    def test_check_resources_disk_error(self, mock_usage: MagicMock) -> None:
        """Test resource check with insufficient disk space."""
        mock_usage.return_value = ResourceUsage(
            cpu_percent=25.0,
            memory_total_gb=16.0,
            memory_available_gb=8.0,
            memory_percent=50.0,
            disk_total_gb=50.0,
            disk_available_gb=5.0,  # Below 10 GB minimum
            disk_percent=90.0,
        )

        result = check_minimum_resources()

        assert result.passed is False
        assert len(result.errors) == 1
        assert "Insufficient disk space" in result.errors[0]

    @patch("app.core.resources.get_current_usage")
    def test_check_resources_memory_warning(self, mock_usage: MagicMock) -> None:
        """Test resource check with low memory warning."""
        mock_usage.return_value = ResourceUsage(
            cpu_percent=25.0,
            memory_total_gb=4.0,
            memory_available_gb=1.5,  # Above 1 GB but below 2 GB warning
            memory_percent=62.5,
            disk_total_gb=500.0,
            disk_available_gb=250.0,
            disk_percent=50.0,
        )

        result = check_minimum_resources()

        assert result.passed is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 1
        assert "Low memory" in result.warnings[0]

    @patch("app.core.resources.get_current_usage")
    def test_check_resources_disk_warning(self, mock_usage: MagicMock) -> None:
        """Test resource check with low disk warning."""
        mock_usage.return_value = ResourceUsage(
            cpu_percent=25.0,
            memory_total_gb=16.0,
            memory_available_gb=8.0,
            memory_percent=50.0,
            disk_total_gb=100.0,
            disk_available_gb=15.0,  # Above 10 GB but below 20 GB warning
            disk_percent=85.0,
        )

        result = check_minimum_resources()

        assert result.passed is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 1
        assert "Low disk space" in result.warnings[0]

    @patch("app.core.resources.get_current_usage")
    def test_check_resources_multiple_errors(self, mock_usage: MagicMock) -> None:
        """Test resource check with multiple failures."""
        mock_usage.return_value = ResourceUsage(
            cpu_percent=95.0,
            memory_total_gb=2.0,
            memory_available_gb=0.5,  # Below minimum
            memory_percent=75.0,
            disk_total_gb=20.0,
            disk_available_gb=5.0,  # Below minimum
            disk_percent=75.0,
        )

        result = check_minimum_resources()

        assert result.passed is False
        assert len(result.errors) == 2

    @patch("app.core.resources.get_current_usage")
    def test_check_resources_custom_requirements(self, mock_usage: MagicMock) -> None:
        """Test resource check with custom requirements."""
        mock_usage.return_value = ResourceUsage(
            cpu_percent=25.0,
            memory_total_gb=4.0,
            memory_available_gb=3.0,  # Would fail with 4 GB requirement
            memory_percent=25.0,
            disk_total_gb=100.0,
            disk_available_gb=40.0,
            disk_percent=60.0,
        )

        # Stricter requirements
        requirements = ResourceRequirements(
            min_memory_gb=4.0,
            min_disk_gb=50.0,
            warn_memory_gb=8.0,
            warn_disk_gb=100.0,
        )

        result = check_minimum_resources(requirements=requirements)

        assert result.passed is False
        assert len(result.errors) == 2  # Both memory and disk fail

    @patch("app.core.resources.get_current_usage")
    def test_check_resources_returns_usage(self, mock_usage: MagicMock) -> None:
        """Test that check returns current usage."""
        expected_usage = ResourceUsage(
            cpu_percent=25.0,
            memory_total_gb=16.0,
            memory_available_gb=8.0,
            memory_percent=50.0,
            disk_total_gb=500.0,
            disk_available_gb=250.0,
            disk_percent=50.0,
        )
        mock_usage.return_value = expected_usage

        result = check_minimum_resources()

        assert result.usage == expected_usage


class TestResourceCheckResult:
    """Tests for ResourceCheckResult dataclass."""

    def test_result_passed(self) -> None:
        """Test result with passed check."""
        usage = ResourceUsage(
            cpu_percent=25.0,
            memory_total_gb=16.0,
            memory_available_gb=8.0,
            memory_percent=50.0,
            disk_total_gb=500.0,
            disk_available_gb=250.0,
            disk_percent=50.0,
        )
        result = ResourceCheckResult(
            passed=True,
            usage=usage,
            errors=[],
            warnings=[],
        )

        assert result.passed is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_result_failed(self) -> None:
        """Test result with failed check."""
        usage = ResourceUsage(
            cpu_percent=95.0,
            memory_total_gb=2.0,
            memory_available_gb=0.5,
            memory_percent=75.0,
            disk_total_gb=20.0,
            disk_available_gb=5.0,
            disk_percent=75.0,
        )
        result = ResourceCheckResult(
            passed=False,
            usage=usage,
            errors=["Insufficient memory", "Insufficient disk"],
            warnings=[],
        )

        assert result.passed is False
        assert len(result.errors) == 2
