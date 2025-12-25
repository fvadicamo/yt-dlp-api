"""Resource monitoring and validation.

This module provides functions to monitor system resources (CPU, memory, disk)
and validate that minimum requirements are met for stable operation.

Implements requirements:
- Req 47: Graceful Startup Mode (resource validation)
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import psutil
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ResourceUsage:
    """Current system resource usage.

    Attributes:
        cpu_percent: Current CPU usage percentage (0-100).
        memory_total_gb: Total system memory in GB.
        memory_available_gb: Available memory in GB.
        memory_percent: Memory usage percentage (0-100).
        disk_total_gb: Total disk space in GB for the specified path.
        disk_available_gb: Available disk space in GB.
        disk_percent: Disk usage percentage (0-100).
    """

    cpu_percent: float
    memory_total_gb: float
    memory_available_gb: float
    memory_percent: float
    disk_total_gb: float
    disk_available_gb: float
    disk_percent: float


@dataclass
class ResourceRequirements:
    """Minimum resource requirements.

    Attributes:
        min_memory_gb: Minimum required memory in GB.
        min_disk_gb: Minimum required disk space in GB.
        warn_memory_gb: Memory threshold for warning in GB.
        warn_disk_gb: Disk threshold for warning in GB.
    """

    min_memory_gb: float = 1.0
    min_disk_gb: float = 10.0
    warn_memory_gb: float = 2.0
    warn_disk_gb: float = 20.0


@dataclass
class ResourceCheckResult:
    """Result of resource validation.

    Attributes:
        passed: Whether minimum requirements are met.
        usage: Current resource usage.
        errors: List of critical resource issues.
        warnings: List of resource warnings.
    """

    passed: bool
    usage: ResourceUsage
    errors: list[str]
    warnings: list[str]


def get_current_usage(disk_path: Optional[str] = None) -> ResourceUsage:
    """Get current system resource usage.

    Args:
        disk_path: Path to check disk usage for. Defaults to root filesystem.

    Returns:
        ResourceUsage with current resource metrics.
    """
    # CPU usage (1 second interval for accuracy)
    cpu_percent = psutil.cpu_percent(interval=0.1)

    # Memory usage
    memory = psutil.virtual_memory()
    memory_total_gb = memory.total / (1024**3)
    memory_available_gb = memory.available / (1024**3)
    memory_percent = memory.percent

    # Disk usage
    path = Path(disk_path) if disk_path else Path("/")
    if not path.exists():
        path = Path("/")

    disk = psutil.disk_usage(str(path))
    disk_total_gb = disk.total / (1024**3)
    disk_available_gb = disk.free / (1024**3)
    disk_percent = disk.percent

    return ResourceUsage(
        cpu_percent=round(cpu_percent, 1),
        memory_total_gb=round(memory_total_gb, 2),
        memory_available_gb=round(memory_available_gb, 2),
        memory_percent=round(memory_percent, 1),
        disk_total_gb=round(disk_total_gb, 2),
        disk_available_gb=round(disk_available_gb, 2),
        disk_percent=round(disk_percent, 1),
    )


def check_minimum_resources(
    disk_path: Optional[str] = None,
    requirements: Optional[ResourceRequirements] = None,
) -> ResourceCheckResult:
    """Check if minimum resource requirements are met.

    Args:
        disk_path: Path to check disk usage for.
        requirements: Resource requirements. Uses defaults if not specified.

    Returns:
        ResourceCheckResult with validation status and any issues.
    """
    if requirements is None:
        requirements = ResourceRequirements()

    usage = get_current_usage(disk_path)
    errors = []
    warnings = []

    # Check memory
    if usage.memory_available_gb < requirements.min_memory_gb:
        errors.append(
            f"Insufficient memory: {usage.memory_available_gb:.1f}GB available, "
            f"minimum {requirements.min_memory_gb:.1f}GB required"
        )
    elif usage.memory_available_gb < requirements.warn_memory_gb:
        warnings.append(
            f"Low memory: {usage.memory_available_gb:.1f}GB available, "
            f"recommended {requirements.warn_memory_gb:.1f}GB"
        )

    # Check disk
    if usage.disk_available_gb < requirements.min_disk_gb:
        errors.append(
            f"Insufficient disk space: {usage.disk_available_gb:.1f}GB available, "
            f"minimum {requirements.min_disk_gb:.1f}GB required"
        )
    elif usage.disk_available_gb < requirements.warn_disk_gb:
        warnings.append(
            f"Low disk space: {usage.disk_available_gb:.1f}GB available, "
            f"recommended {requirements.warn_disk_gb:.1f}GB"
        )

    passed = len(errors) == 0

    if errors:
        logger.error(
            "resource_check_failed",
            errors=errors,
            memory_available_gb=usage.memory_available_gb,
            disk_available_gb=usage.disk_available_gb,
        )
    elif warnings:
        logger.warning(
            "resource_check_warnings",
            warnings=warnings,
            memory_available_gb=usage.memory_available_gb,
            disk_available_gb=usage.disk_available_gb,
        )
    else:
        logger.info(
            "resource_check_passed",
            memory_available_gb=usage.memory_available_gb,
            disk_available_gb=usage.disk_available_gb,
        )

    return ResourceCheckResult(
        passed=passed,
        usage=usage,
        errors=errors,
        warnings=warnings,
    )
