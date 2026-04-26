"""WebhookPort: notify the platform of pipeline completion."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from grabatus_service_core.contract.callback import Callback
    from grabatus_service_core.ports.values import WebhookAck


@runtime_checkable
class WebhookPort(Protocol):
    """Send a JWT-signed POST to the platform's webhook URL."""

    def notify(self, *, callback: Callback, payload: dict[str, Any]) -> WebhookAck:
        """POST ``payload`` to ``callback.url`` with a signed Authorization."""
        ...
