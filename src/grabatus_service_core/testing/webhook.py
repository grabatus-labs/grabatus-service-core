"""RecordingWebhookNotifier: records every notify call for inspection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from grabatus_service_core.ports.values import WebhookAck

if TYPE_CHECKING:
    from grabatus_service_core.contract.callback import Callback


@dataclass(frozen=True, slots=True)
class RecordedWebhookCall:
    callback: Callback
    payload: dict[str, Any]


@dataclass
class RecordingWebhookNotifier:
    """Captures every webhook call to ``calls`` for assertions."""

    default_status: int = 200
    default_body: str = "ok"
    calls: list[RecordedWebhookCall] = field(default_factory=list)

    def notify(
        self,
        *,
        callback: Callback,
        payload: dict[str, Any],
    ) -> WebhookAck:
        self.calls.append(
            RecordedWebhookCall(callback=callback, payload=dict(payload)),
        )
        return WebhookAck(
            http_status=self.default_status,
            response_body=self.default_body,
        )
