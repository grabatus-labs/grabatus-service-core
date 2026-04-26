"""PubSubMessagePort: decode Cloud Pub/Sub push envelopes to dicts and back."""

from __future__ import annotations

import base64
import binascii
import json
from typing import TYPE_CHECKING, Any

from grabatus_service_core.errors import MalformedMessageError

if TYPE_CHECKING:
    from grabatus_service_core.ports.values import RawMessage


_MESSAGE_KEY = "message"
_DATA_KEY = "data"


class PubSubMessagePort:
    """Translate between Pub/Sub push envelopes and Python dicts.

    Pub/Sub push HTTP delivery wraps the payload as
    ``{"message": {"data": "<base64-of-json>"}}`` plus optional attributes.
    The decoder pulls out and decodes ``data``; the encoder produces the
    same shape for tests and worker dispatch.
    """

    def decode(self, raw: RawMessage) -> dict[str, Any]:
        try:
            envelope = json.loads(raw.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MalformedMessageError(
                f"PubSub envelope is not valid UTF-8 JSON: {exc}",
            ) from exc
        if not isinstance(envelope, dict):
            raise MalformedMessageError(
                f"PubSub envelope must be a JSON object, got type={type(envelope).__name__}",
            )
        message = envelope.get(_MESSAGE_KEY)
        if not isinstance(message, dict):
            raise MalformedMessageError(
                f"PubSub envelope is missing 'message' object; got keys={sorted(envelope)!r}",
            )
        encoded = message.get(_DATA_KEY)
        if not isinstance(encoded, str):
            raise MalformedMessageError(
                f"PubSub message.data must be a base64 string, got type={type(encoded).__name__}",
            )
        try:
            decoded_bytes = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise MalformedMessageError(
                f"PubSub message.data is not valid base64: {exc}",
            ) from exc
        try:
            payload = json.loads(decoded_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MalformedMessageError(
                f"PubSub decoded payload is not valid UTF-8 JSON: {exc}",
            ) from exc
        if not isinstance(payload, dict):
            raise MalformedMessageError(
                f"PubSub decoded payload must be a JSON object, got type={type(payload).__name__}",
            )
        return payload

    def encode(self, envelope: dict[str, Any]) -> bytes:
        encoded_payload = base64.b64encode(json.dumps(envelope).encode("utf-8")).decode("ascii")
        wrapper = {_MESSAGE_KEY: {_DATA_KEY: encoded_payload}}
        return json.dumps(wrapper).encode("utf-8")
