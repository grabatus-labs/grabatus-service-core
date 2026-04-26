"""InMemoryMessagePort: JSON-encoded round-trip without Pub/Sub envelope."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from grabatus_service_core.ports.values import RawMessage


class InMemoryMessagePort:
    """Encode/decode dicts as raw UTF-8 JSON bytes — no Pub/Sub envelope."""

    def decode(self, raw: RawMessage) -> dict[str, Any]:
        decoded = json.loads(raw.payload.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError(
                f"InMemoryMessagePort.decode expected dict, got type={type(decoded).__name__}",
            )
        return decoded

    def encode(self, envelope: dict[str, Any]) -> bytes:
        return json.dumps(envelope).encode("utf-8")
