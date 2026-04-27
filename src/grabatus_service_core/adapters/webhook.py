"""JwtWebhookNotifier: signed POST to the platform's webhook URL via httpx."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
from opentelemetry.propagate import inject as _otel_inject

from grabatus_service_core.adapters.retry import with_retry
from grabatus_service_core.errors import WebhookAuthError, WebhookError
from grabatus_service_core.ports.values import WebhookAck
from grabatus_service_core.security.jwt_helpers import encode_hs256

if TYPE_CHECKING:
    from grabatus_service_core.contract.callback import Callback


_AUTH_FAILURE_STATUSES = frozenset({401, 403})
_DEFAULT_TIMEOUT_SECONDS = 15.0
_HTTP_OK_LOWER_BOUND = 200
_HTTP_OK_UPPER_BOUND = 300
_RETRIABLE_HTTP_ERRORS: tuple[type[BaseException], ...] = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
)


class JwtWebhookNotifier:
    """Signs the payload with HS256 and POSTs it to ``callback.url``.

    The signing secret is supplied per call (via ``Credentials`` resolved
    from the contract's ``callback.credential_ref``) so that the notifier
    is stateless across requests.
    """

    def __init__(
        self,
        *,
        signing_secret: bytes,
        client: httpx.Client | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._signing_secret = signing_secret
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._timeout = timeout_seconds

    @with_retry(retry_on=_RETRIABLE_HTTP_ERRORS)
    def notify(
        self,
        *,
        callback: Callback,
        payload: dict[str, Any],
    ) -> WebhookAck:
        token = encode_hs256(payload=payload, secret=self._signing_secret)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        _otel_inject(headers)
        url = str(callback.url)
        try:
            response = self._client.post(
                url,
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )
        except _RETRIABLE_HTTP_ERRORS:
            raise
        except httpx.HTTPError as exc:
            raise WebhookError(
                f"Webhook POST to url={url!r} failed: {exc}",
            ) from exc
        if response.status_code in _AUTH_FAILURE_STATUSES:
            raise WebhookAuthError(
                f"Webhook url={url!r} rejected JWT (status={response.status_code})",
            )
        if not (_HTTP_OK_LOWER_BOUND <= response.status_code < _HTTP_OK_UPPER_BOUND):
            raise WebhookError(
                f"Webhook url={url!r} returned non-2xx status={response.status_code}",
            )
        return WebhookAck(http_status=response.status_code, response_body=response.text)
