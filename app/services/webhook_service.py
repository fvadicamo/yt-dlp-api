"""Job completion webhook delivery.

Sends HMAC-signed POST notifications to consumer-provided URLs when a
download job reaches a terminal state, so downstream systems (workflow
engines, data platforms, external STT pipelines) don't need to poll
GET /jobs/{id}.

SSRF protection: webhooks are disabled by default and, when enabled,
the target host must appear in the configured allowlist. Redirects are
never followed.
"""

import asyncio
import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
import structlog

from app.core.metrics import MetricsCollector

logger = structlog.get_logger(__name__)


@dataclass
class WebhookValidationResult:
    """Result of validating a webhook URL against the configuration."""

    is_valid: bool
    error_message: Optional[str] = None


class WebhookService:
    """Validates webhook URLs and delivers signed job notifications."""

    SIGNATURE_HEADER = "X-Webhook-Signature"
    EVENT_HEADER = "X-Webhook-Event"
    DELIVERY_HEADER = "X-Webhook-Delivery"

    def __init__(
        self,
        enabled: bool = False,
        allowed_hosts: Optional[List[str]] = None,
        secret: Optional[str] = None,
        timeout: float = 5.0,
        max_retries: int = 3,
    ) -> None:
        """Initialize the webhook service.

        Args:
            enabled: Master switch; when False every webhook URL is rejected.
            allowed_hosts: Exact hostnames allowed as webhook targets.
            secret: HMAC-SHA256 key; when set, deliveries carry a signature.
            timeout: Seconds per delivery attempt.
            max_retries: Total delivery attempts before giving up.
        """
        self.enabled = enabled
        self.allowed_hosts = allowed_hosts or []
        self.secret = secret
        self.timeout = timeout
        self.max_retries = max_retries

    def validate_url(self, webhook_url: str) -> WebhookValidationResult:
        """Validate a webhook URL against the configuration.

        Args:
            webhook_url: Target URL provided by the API consumer.

        Returns:
            Validation result with a reason when rejected.
        """
        if not self.enabled:
            return WebhookValidationResult(
                is_valid=False,
                error_message="Webhooks are disabled on this server",
            )

        parsed = urlparse(webhook_url)
        if parsed.scheme not in ("http", "https"):
            return WebhookValidationResult(
                is_valid=False,
                error_message="Webhook URL must use http or https",
            )

        if not parsed.hostname:
            return WebhookValidationResult(
                is_valid=False,
                error_message="Webhook URL has no hostname",
            )

        if parsed.hostname not in self.allowed_hosts:
            return WebhookValidationResult(
                is_valid=False,
                error_message=(
                    f"Webhook host '{parsed.hostname}' is not in the allowed hosts list"
                ),
            )

        return WebhookValidationResult(is_valid=True)

    def _sign(self, body: bytes) -> Optional[str]:
        """Compute the HMAC-SHA256 signature header value for a body."""
        if not self.secret:
            return None
        digest = hmac.new(self.secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    async def deliver(self, webhook_url: str, event: str, payload: Dict[str, Any]) -> bool:
        """Deliver a webhook notification with retries.

        Args:
            webhook_url: Target URL (must have passed validate_url).
            event: Event name (e.g. "job.completed", "job.failed").
            payload: JSON-serializable notification body.

        Returns:
            True when a 2xx response was received, False otherwise.
        """
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            self.EVENT_HEADER: event,
            self.DELIVERY_HEADER: str(uuid.uuid4()),
        }
        signature = self._sign(body)
        if signature:
            headers[self.SIGNATURE_HEADER] = signature

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout, follow_redirects=False
                ) as client:
                    response = await client.post(webhook_url, content=body, headers=headers)

                if 200 <= response.status_code < 300:
                    logger.info(
                        "webhook_delivered",
                        webhook_event=event,
                        status_code=response.status_code,
                        attempt=attempt,
                    )
                    MetricsCollector.record_webhook_delivery(event=event, status="success")
                    return True

                logger.warning(
                    "webhook_delivery_rejected",
                    webhook_event=event,
                    status_code=response.status_code,
                    attempt=attempt,
                )

            except httpx.HTTPError as e:
                logger.warning(
                    "webhook_delivery_error",
                    webhook_event=event,
                    error=str(e),
                    attempt=attempt,
                )

            if attempt < self.max_retries:
                await asyncio.sleep(2 ** (attempt - 1))

        logger.error("webhook_delivery_failed", webhook_event=event, attempts=self.max_retries)
        MetricsCollector.record_webhook_delivery(event=event, status="failed")
        return False


# Global webhook service instance
_webhook_service: Optional[WebhookService] = None


def configure_webhook_service(
    enabled: bool = False,
    allowed_hosts: Optional[List[str]] = None,
    secret: Optional[str] = None,
    timeout: float = 5.0,
    max_retries: int = 3,
) -> WebhookService:
    """Configure and initialize the global webhook service."""
    global _webhook_service
    _webhook_service = WebhookService(
        enabled=enabled,
        allowed_hosts=allowed_hosts,
        secret=secret,
        timeout=timeout,
        max_retries=max_retries,
    )
    return _webhook_service


def get_webhook_service() -> WebhookService:
    """Get the global webhook service instance.

    Returns:
        The configured WebhookService, or a disabled default when the
        application has not configured one (e.g. bare test apps).
    """
    if _webhook_service is None:
        return WebhookService(enabled=False)
    return _webhook_service
