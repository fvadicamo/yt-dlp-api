"""Tests for the webhook delivery service (validation, signing, retries)."""

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import app.services.webhook_service as webhook_module
from app.services.webhook_service import (
    WebhookService,
    configure_webhook_service,
    get_webhook_service,
)


def _mock_async_client(post_results):
    """Build an httpx.AsyncClient factory yielding queued post results.

    Args:
        post_results: List of responses or exceptions, one per post call.
    """
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.post = AsyncMock(side_effect=post_results)
    return MagicMock(return_value=client), client


def _response(status_code: int) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    return response


class TestValidateUrl:
    """Webhook URL validation (SSRF protection)."""

    def test_disabled_rejects_everything(self):
        """When disabled, every URL is rejected."""
        service = WebhookService(enabled=False, allowed_hosts=["hooks.example.com"])

        result = service.validate_url("https://hooks.example.com/x")

        assert result.is_valid is False
        assert "disabled" in result.error_message

    def test_allowed_host_accepted(self):
        """Enabled service accepts hosts from the allowlist."""
        service = WebhookService(enabled=True, allowed_hosts=["hooks.example.com"])

        assert service.validate_url("https://hooks.example.com/notify").is_valid is True

    def test_host_not_in_allowlist_rejected(self):
        """Hosts outside the allowlist are rejected."""
        service = WebhookService(enabled=True, allowed_hosts=["hooks.example.com"])

        result = service.validate_url("https://evil.example.net/x")

        assert result.is_valid is False
        assert "not in the allowed hosts" in result.error_message

    def test_empty_allowlist_rejects_all(self):
        """Enabled with an empty allowlist still rejects everything."""
        service = WebhookService(enabled=True, allowed_hosts=[])

        assert service.validate_url("https://hooks.example.com/x").is_valid is False

    @pytest.mark.parametrize("url", ["ftp://hooks.example.com/x", "file:///etc/passwd", "hooks"])
    def test_invalid_schemes_rejected(self, url):
        """Non-http(s) schemes and hostless URLs are rejected."""
        service = WebhookService(enabled=True, allowed_hosts=["hooks.example.com"])

        assert service.validate_url(url).is_valid is False


class TestDelivery:
    """Delivery semantics: signing, retries, outcomes."""

    @pytest.mark.asyncio
    async def test_successful_delivery_signs_payload(self):
        """A 2xx response returns True; HMAC signature matches the body."""
        factory, client = _mock_async_client([_response(200)])
        service = WebhookService(
            enabled=True, allowed_hosts=["h"], secret="topsecret", max_retries=3
        )

        with patch.object(webhook_module.httpx, "AsyncClient", factory):
            ok = await service.deliver(
                "https://h/notify", "job.completed", {"job_id": "j1", "status": "completed"}
            )

        assert ok is True
        client.post.assert_awaited_once()
        kwargs = client.post.call_args.kwargs
        body = kwargs["content"]
        headers = kwargs["headers"]
        expected = hmac.new(b"topsecret", body, hashlib.sha256).hexdigest()
        assert headers["X-Webhook-Signature"] == f"sha256={expected}"
        assert headers["X-Webhook-Event"] == "job.completed"
        assert headers["X-Webhook-Delivery"]
        assert json.loads(body)["job_id"] == "j1"

    @pytest.mark.asyncio
    async def test_no_signature_without_secret(self):
        """Without a secret no signature header is sent."""
        factory, client = _mock_async_client([_response(204)])
        service = WebhookService(enabled=True, allowed_hosts=["h"], secret=None)

        with patch.object(webhook_module.httpx, "AsyncClient", factory):
            ok = await service.deliver("https://h/notify", "job.completed", {})

        assert ok is True
        assert "X-Webhook-Signature" not in client.post.call_args.kwargs["headers"]

    @pytest.mark.asyncio
    async def test_retry_then_success(self):
        """A transient error retries with backoff and succeeds."""
        factory, client = _mock_async_client([httpx.ConnectError("refused"), _response(200)])
        service = WebhookService(enabled=True, allowed_hosts=["h"], max_retries=3)

        with (
            patch.object(webhook_module.httpx, "AsyncClient", factory),
            patch.object(webhook_module.asyncio, "sleep", new_callable=AsyncMock) as sleep,
        ):
            ok = await service.deliver("https://h/notify", "job.completed", {})

        assert ok is True
        assert client.post.await_count == 2
        sleep.assert_awaited_once_with(1)

    @pytest.mark.asyncio
    async def test_all_attempts_fail(self):
        """Exhausted retries return False and record a failed metric."""
        factory, client = _mock_async_client(
            [_response(500), _response(502), httpx.ReadTimeout("slow")]
        )
        service = WebhookService(enabled=True, allowed_hosts=["h"], max_retries=3)

        with (
            patch.object(webhook_module.httpx, "AsyncClient", factory),
            patch.object(webhook_module.asyncio, "sleep", new_callable=AsyncMock),
            patch.object(webhook_module.MetricsCollector, "record_webhook_delivery") as record,
        ):
            ok = await service.deliver("https://h/notify", "job.failed", {})

        assert ok is False
        assert client.post.await_count == 3
        record.assert_called_once_with(event="job.failed", status="failed")


class TestGlobalService:
    """Global configure/get helpers."""

    @pytest.fixture(autouse=True)
    def reset_global(self):
        """Save and restore the module-level instance."""
        saved = webhook_module._webhook_service
        webhook_module._webhook_service = None
        yield
        webhook_module._webhook_service = saved

    def test_unconfigured_returns_disabled_service(self):
        """Without configuration a disabled service is returned."""
        service = get_webhook_service()

        assert service.enabled is False
        assert service.validate_url("https://any.example.com/x").is_valid is False

    def test_configure_roundtrip(self):
        """configure_webhook_service installs the global instance."""
        service = configure_webhook_service(
            enabled=True, allowed_hosts=["hooks.example.com"], secret="s"
        )

        assert get_webhook_service() is service
        assert get_webhook_service().enabled is True
