"""MessagePort: decode broker envelopes to raw dicts and back."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from grabatus_service_core.ports.values import RawMessage


@runtime_checkable
class MessagePort(Protocol):
    """Translate between broker wire format and Python dicts.

    The runner calls ``decode`` on incoming bytes, then hands the dict to
    ``BaseServiceContract.model_validate``. Adapters wrap Pub/Sub envelopes
    (base64 + JSON) or in-memory dicts (tests).
    """

    def decode(self, raw: RawMessage) -> dict[str, Any]:
        """Parse the broker envelope to a Python dict."""
        ...

    def encode(self, envelope: dict[str, Any]) -> bytes:
        """Serialize a Python dict back to broker wire format."""
        ...
