"""Errors raised when notifying the Grabatus webhook."""

from __future__ import annotations

from grabatus_service_core.errors.base import GrabatusServiceError


class WebhookError(GrabatusServiceError):
    """Base for webhook failures."""

    error_code = "webhook_failed"
    http_status = 200
    retriable = True


class WebhookAuthError(WebhookError):
    """Webhook returned 401/403 — JWT was rejected."""

    error_code = "webhook_auth_failed"
    retriable = False
