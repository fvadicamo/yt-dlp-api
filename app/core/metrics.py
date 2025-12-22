"""Prometheus metrics collection for the API.

This module defines and manages Prometheus metrics for monitoring
request rates, download operations, queue status, storage, and errors.

Implements Requirement 29: Prometheus Metrics Export.
"""

from prometheus_client import Counter, Gauge, Histogram, Info

# Application info
app_info = Info("ytdlp_api", "YT-DLP API application information")

# HTTP request metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

# Download metrics
downloads_total = Counter(
    "downloads_total",
    "Total download operations by provider and status",
    ["provider", "status"],
)

download_duration_seconds = Histogram(
    "download_duration_seconds",
    "Download duration in seconds",
    ["provider"],
    buckets=[10.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1200.0],
)

download_size_bytes = Histogram(
    "download_size_bytes",
    "Downloaded file size in bytes",
    ["provider"],
    buckets=[1e6, 10e6, 50e6, 100e6, 250e6, 500e6, 1e9, 2e9],
)

# Queue metrics
download_queue_size = Gauge(
    "download_queue_size",
    "Current number of jobs in the download queue",
)

concurrent_downloads = Gauge(
    "concurrent_downloads",
    "Number of currently active downloads",
)

# Storage metrics
storage_used_bytes = Gauge(
    "storage_used_bytes",
    "Total storage space used in bytes",
)

storage_available_bytes = Gauge(
    "storage_available_bytes",
    "Available storage space in bytes",
)

storage_percent_used = Gauge(
    "storage_percent_used",
    "Storage usage as a percentage (0-100)",
)

# Error metrics
errors_total = Counter(
    "errors_total",
    "Total errors by error code and endpoint",
    ["error_code", "endpoint"],
)

# Rate limiting metrics
rate_limit_exceeded_total = Counter(
    "rate_limit_exceeded_total",
    "Total rate limit exceeded events",
    ["api_key_hash", "category"],
)

# Cookie metrics
cookie_age_seconds = Gauge(
    "cookie_age_seconds",
    "Age of cookie file in seconds",
    ["provider"],
)

cookie_validation_total = Counter(
    "cookie_validation_total",
    "Total cookie validation attempts by result",
    ["provider", "result"],
)


class MetricsCollector:
    """Centralized metrics collection and update helper.

    Provides static methods for recording various metrics throughout
    the application in a consistent manner.
    """

    @staticmethod
    def record_request(
        method: str,
        endpoint: str,
        status: int,
        duration: float,
    ) -> None:
        """Record HTTP request metrics.

        Args:
            method: HTTP method (GET, POST, etc.).
            endpoint: Normalized endpoint path.
            status: HTTP response status code.
            duration: Request duration in seconds.
        """
        http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status=str(status),
        ).inc()
        http_request_duration_seconds.labels(
            method=method,
            endpoint=endpoint,
        ).observe(duration)

    @staticmethod
    def record_download(
        provider: str,
        status: str,
        duration: float,
        size: int,
    ) -> None:
        """Record download operation metrics.

        Args:
            provider: Provider name (e.g., 'youtube').
            status: Download status ('success' or 'failed').
            duration: Download duration in seconds.
            size: Downloaded file size in bytes.
        """
        downloads_total.labels(provider=provider, status=status).inc()
        download_duration_seconds.labels(provider=provider).observe(duration)
        if size > 0:
            download_size_bytes.labels(provider=provider).observe(size)

    @staticmethod
    def update_queue_metrics(queue_size: int, active_downloads: int) -> None:
        """Update download queue metrics.

        Args:
            queue_size: Current number of jobs in queue.
            active_downloads: Number of active download operations.
        """
        download_queue_size.set(queue_size)
        concurrent_downloads.set(active_downloads)

    @staticmethod
    def update_storage_metrics(
        used: int,
        available: int,
        percent: float,
    ) -> None:
        """Update storage metrics.

        Args:
            used: Storage space used in bytes.
            available: Available storage space in bytes.
            percent: Storage usage percentage (0-100).
        """
        storage_used_bytes.set(used)
        storage_available_bytes.set(available)
        storage_percent_used.set(percent)

    @staticmethod
    def record_error(error_code: str, endpoint: str) -> None:
        """Record an error occurrence.

        Args:
            error_code: Error code from ErrorCode class.
            endpoint: Endpoint where the error occurred.
        """
        errors_total.labels(error_code=error_code, endpoint=endpoint).inc()

    @staticmethod
    def record_rate_limit_exceeded(api_key_hash: str, category: str) -> None:
        """Record a rate limit exceeded event.

        Args:
            api_key_hash: Hashed API key (for privacy).
            category: Rate limit category ('metadata' or 'download').
        """
        rate_limit_exceeded_total.labels(
            api_key_hash=api_key_hash,
            category=category,
        ).inc()

    @staticmethod
    def update_cookie_age(provider: str, age_seconds: float) -> None:
        """Update cookie file age metric.

        Args:
            provider: Provider name.
            age_seconds: Age of cookie file in seconds.
        """
        cookie_age_seconds.labels(provider=provider).set(age_seconds)

    @staticmethod
    def record_cookie_validation(provider: str, result: str) -> None:
        """Record a cookie validation attempt.

        Args:
            provider: Provider name.
            result: Validation result ('valid', 'invalid', 'error').
        """
        cookie_validation_total.labels(provider=provider, result=result).inc()


def initialize_metrics(version: str) -> None:
    """Initialize application metrics with version information.

    Should be called during application startup.

    Args:
        version: Application version string.
    """
    app_info.info({"version": version})
