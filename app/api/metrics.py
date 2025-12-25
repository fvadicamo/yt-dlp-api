"""Prometheus metrics endpoint.

This module provides the /metrics endpoint for Prometheus scraping.

Implements Requirement 29: Prometheus Metrics Export.
"""

from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter(tags=["monitoring"])


@router.get(
    "/metrics",
    response_class=Response,
    summary="Prometheus metrics endpoint",
    description="Returns metrics in Prometheus text format for scraping. "
    "This endpoint does not require authentication.",
)
async def metrics() -> Response:
    """Prometheus metrics endpoint.

    Returns all application metrics in Prometheus text exposition format.
    This endpoint is intentionally unauthenticated to allow Prometheus
    to scrape metrics without requiring API key configuration.

    Returns:
        Response with Prometheus metrics in text format.
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
