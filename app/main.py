"""FastAPI application entry point.

This module assembles all components and creates the main application.
Implements requirements 12, 16, 19, 20, 29, 39, and 46.
"""

import asyncio
import contextlib
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app import __version__
from app.api import admin, download, health, jobs, metrics, video
from app.core.config import ConfigService, SecurityConfig
from app.core.errors import APIError, global_exception_handler
from app.core.logging import configure_logging
from app.core.metrics import MetricsCollector, initialize_metrics
from app.core.rate_limiter import configure_rate_limiter
from app.middleware.auth import configure_auth
from app.middleware.rate_limit import RateLimitMiddleware
from app.providers.manager import ProviderManager
from app.providers.youtube import YouTubeProvider
from app.services.cookie_service import CookieService
from app.services.download_queue import configure_download_queue, get_download_queue
from app.services.download_worker import configure_download_worker, get_download_worker
from app.services.job_service import configure_job_service, get_job_service
from app.services.storage import configure_storage

logger = structlog.get_logger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to track HTTP request metrics.

    Records request count and duration for all endpoints,
    using FastAPI route templates to normalize paths.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process request and record metrics."""
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time

        # Use FastAPI route template for normalized endpoint path
        # Use fixed label for unmatched routes to prevent unbounded cardinality
        route = request.scope.get("route")
        endpoint = route.path if route else "/unmatched"

        MetricsCollector.record_request(
            method=request.method,
            endpoint=endpoint,
            status=response.status_code,
            duration=duration,
        )

        return response


# Global service instances
_provider_manager: ProviderManager | None = None
_cookie_service: CookieService | None = None
_cleanup_task: asyncio.Task | None = None


def get_provider_manager() -> ProviderManager:
    """Get the global provider manager instance."""
    if _provider_manager is None:
        raise RuntimeError("Provider manager not configured")
    return _provider_manager


def get_cookie_service() -> CookieService:
    """Get the global cookie service instance."""
    if _cookie_service is None:
        raise RuntimeError("Cookie service not configured")
    return _cookie_service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown."""
    global _provider_manager, _cookie_service, _cleanup_task

    logger.info("Application starting", version=__version__)

    # Initialize metrics with application version
    initialize_metrics(__version__)

    # Load configuration
    config_service = ConfigService()
    config = config_service.load()

    # Configure logging
    configure_logging(config.logging.level, config.logging.format)

    logger.info(
        "Configuration loaded",
        server_port=config.server.port,
        output_dir=config.storage.output_dir,
    )

    # Configure authentication
    configure_auth(api_keys=config.security.api_keys)

    # Configure rate limiter
    configure_rate_limiter(
        metadata_rpm=config.rate_limiting.metadata_rpm,
        download_rpm=config.rate_limiting.download_rpm,
        burst_capacity=config.rate_limiting.burst_capacity,
    )

    # Configure storage manager
    storage = configure_storage(config.storage)
    logger.info("Storage manager configured", output_dir=config.storage.output_dir)

    # Configure job service with callback to unregister files on job expiry
    def on_job_expired(job_id: str) -> None:
        """Unregister files when a job expires."""
        storage.unregister_active_job(job_id)

    job_service = configure_job_service(
        job_ttl_hours=config.downloads.job_ttl,
        on_job_expired=on_job_expired,
    )
    logger.info("Job service configured", job_ttl_hours=config.downloads.job_ttl)

    # Configure download queue
    download_queue = configure_download_queue(
        max_concurrent=config.downloads.max_concurrent,
        max_queue_size=config.downloads.queue_size,
    )
    logger.info(
        "Download queue configured",
        max_concurrent=config.downloads.max_concurrent,
        max_queue_size=config.downloads.queue_size,
    )

    # Configure cookie service
    cookie_config = {
        "providers": {
            "youtube": {
                "enabled": config.providers.youtube.enabled,
                "cookie_path": config.providers.youtube.cookie_path,
            }
        }
    }
    _cookie_service = CookieService(cookie_config)
    logger.info("Cookie service configured")

    # Configure provider manager and register providers
    _provider_manager = ProviderManager()

    # Register YouTube provider
    if config.providers.youtube.enabled:
        youtube_config = {
            "cookie_path": config.providers.youtube.cookie_path,
            "retry_attempts": config.providers.youtube.retry_attempts,
            "retry_backoff": config.providers.youtube.retry_backoff,
        }
        youtube_provider = YouTubeProvider(youtube_config, _cookie_service)
        _provider_manager.register_provider("youtube", youtube_provider, enabled=True)
        logger.info("YouTube provider registered")

    # Configure download worker
    worker = configure_download_worker(
        provider_manager=_provider_manager,
        job_service=job_service,
        download_queue=download_queue,
        storage_manager=storage,
    )

    # Start download worker
    await worker.start()
    logger.info("Download worker started")

    # Start cleanup scheduler in background
    from app.services.storage import cleanup_scheduler

    _cleanup_task = asyncio.create_task(cleanup_scheduler(storage, interval=3600))
    logger.info("Cleanup scheduler started")

    logger.info("Application startup complete", version=__version__)

    yield

    # Shutdown
    logger.info("Application shutting down")

    # Stop cleanup scheduler
    if _cleanup_task:
        _cleanup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _cleanup_task

    # Stop download worker
    await worker.stop()

    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="YT-DLP REST API",
        description="REST API for video downloads and metadata extraction using yt-dlp",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Add CORS middleware with configurable origins
    # Default ["*"] for development; override via APP_SECURITY_CORS_ORIGINS env var
    security_config = SecurityConfig()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=security_config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add metrics middleware (before rate limiting to capture all requests)
    app.add_middleware(MetricsMiddleware)

    # Add rate limiting middleware
    app.add_middleware(RateLimitMiddleware)

    # Register global exception handlers
    app.add_exception_handler(Exception, global_exception_handler)
    app.add_exception_handler(APIError, global_exception_handler)

    # Override dependency injection for routers

    # Admin router dependencies
    app.dependency_overrides[admin.get_cookie_service] = get_cookie_service

    # Video router dependencies
    app.dependency_overrides[video.get_provider_manager] = get_provider_manager

    # Download router dependencies
    app.dependency_overrides[download.get_provider_manager] = get_provider_manager
    app.dependency_overrides[download.get_job_service] = get_job_service
    app.dependency_overrides[download.get_download_queue] = get_download_queue
    app.dependency_overrides[download.get_download_worker] = get_download_worker

    # Jobs router dependencies
    app.dependency_overrides[jobs.get_job_service] = get_job_service
    app.dependency_overrides[jobs.get_download_queue] = get_download_queue

    # Register routers
    app.include_router(health.router)
    app.include_router(video.router)
    app.include_router(download.router)
    app.include_router(jobs.router)
    app.include_router(admin.router)
    app.include_router(metrics.router)

    return app


# Create the application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn  # type: ignore[import-not-found]

    uvicorn.run(app, host="0.0.0.0", port=8000)  # nosec B104
