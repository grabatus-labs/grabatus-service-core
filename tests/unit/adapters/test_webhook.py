"""Tests for JwtWebhookNotifier (mock httpx)."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from grabatus_service_core.adapters.webhook import JwtWebhookNotifier
from grabatus_service_core.contract.callback import Callback
from grabatus_service_core.errors import WebhookAuthError, WebhookError

_SECRET = b"test-secret-key-at-least-32-bytes-long-padding"


def _callback() -> Callback:
    return Callback.model_validate(
        {"url": "https://grabatus.com/webhook", "auth_scheme": "jwt_hs256"},
    )


def _client_returning(status: int, body: str = "ok") -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.text = body
    client = MagicMock()
    client.post.return_value = response
    return client


def test_notify_signs_payload_and_returns_ack_on_2xx() -> None:
    client = _client_returning(200, "thanks")
    notifier = JwtWebhookNotifier(signing_secret=_SECRET, client=client)

    ack = notifier.notify(
        callback=_callback(),
        payload={"x": 1},
    )

    assert ack.http_status == 200
    assert ack.response_body == "thanks"
    args, kwargs = client.post.call_args
    assert args[0] == "https://grabatus.com/webhook"
    assert kwargs["headers"]["Authorization"].startswith("Bearer ")
    assert kwargs["json"] == {"x": 1}


def test_notify_raises_auth_error_on_401() -> None:
    notifier = JwtWebhookNotifier(signing_secret=_SECRET, client=_client_returning(401))

    with pytest.raises(WebhookAuthError):
        notifier.notify(callback=_callback(), payload={})


def test_notify_raises_auth_error_on_403() -> None:
    notifier = JwtWebhookNotifier(signing_secret=_SECRET, client=_client_returning(403))

    with pytest.raises(WebhookAuthError):
        notifier.notify(callback=_callback(), payload={})


def test_notify_raises_webhook_error_on_500() -> None:
    notifier = JwtWebhookNotifier(signing_secret=_SECRET, client=_client_returning(500))

    with pytest.raises(WebhookError, match="500"):
        notifier.notify(callback=_callback(), payload={})


def test_notify_translates_httpx_error() -> None:
    client = MagicMock()
    client.post.side_effect = httpx.HTTPError("network down")
    notifier = JwtWebhookNotifier(signing_secret=_SECRET, client=client)

    with pytest.raises(WebhookError, match="network down"):
        notifier.notify(callback=_callback(), payload={})


def test_notify_retries_on_timeout_then_succeeds() -> None:
    client = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.text = "ok"
    client.post.side_effect = [httpx.TimeoutException("slow"), response]
    notifier = JwtWebhookNotifier(signing_secret=_SECRET, client=client)

    ack = notifier.notify(callback=_callback(), payload={})

    assert ack.http_status == 200
    assert client.post.call_count == 2


def test_jwt_webhook_includes_traceparent_when_span_active() -> None:
    captured_headers: dict[str, str] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        return httpx.Response(200, text="ok")

    transport = httpx.MockTransport(_handler)
    client = httpx.Client(transport=transport)
    notifier = JwtWebhookNotifier(signing_secret=_SECRET, client=client)

    tp = TracerProvider()
    tp.add_span_processor(SimpleSpanProcessor(InMemorySpanExporter()))
    with tp.get_tracer("test").start_as_current_span("outer"):
        notifier.notify(callback=_callback(), payload={"status": "ok"})

    assert "traceparent" in {k.lower() for k in captured_headers}


def test_jwt_webhook_omits_traceparent_when_no_span() -> None:
    captured_headers: dict[str, str] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        return httpx.Response(200, text="ok")

    transport = httpx.MockTransport(_handler)
    client = httpx.Client(transport=transport)
    notifier = JwtWebhookNotifier(signing_secret=_SECRET, client=client)

    notifier.notify(callback=_callback(), payload={"status": "ok"})

    assert "traceparent" not in {k.lower() for k in captured_headers}
