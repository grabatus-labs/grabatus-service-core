"""Tests for PubSubMessagePort."""

from __future__ import annotations

import base64
import json

import pytest

from grabatus_service_core.adapters.message_pubsub import PubSubMessagePort
from grabatus_service_core.errors import MalformedMessageError
from grabatus_service_core.ports.message import MessagePort
from grabatus_service_core.ports.values import RawMessage


def _envelope_bytes(payload: dict[str, object]) -> bytes:
    encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    return json.dumps({"message": {"data": encoded}}).encode("utf-8")


def test_pubsub_satisfies_port() -> None:
    assert isinstance(PubSubMessagePort(), MessagePort)


def test_decode_round_trips_dict_payload() -> None:
    port = PubSubMessagePort()
    payload = {"k": "v", "n": 1}

    decoded = port.decode(RawMessage(payload=_envelope_bytes(payload)))

    assert decoded == payload


def test_encode_then_decode_round_trip() -> None:
    port = PubSubMessagePort()
    payload = {"a": 1, "b": [1, 2, 3]}

    encoded = port.encode(payload)
    decoded = port.decode(RawMessage(payload=encoded))

    assert decoded == payload


def test_decode_rejects_invalid_json() -> None:
    port = PubSubMessagePort()
    with pytest.raises(MalformedMessageError, match="JSON"):
        port.decode(RawMessage(payload=b"<not json>"))


def test_decode_rejects_top_level_array() -> None:
    port = PubSubMessagePort()
    with pytest.raises(MalformedMessageError, match="JSON object"):
        port.decode(RawMessage(payload=b"[1, 2]"))


def test_decode_rejects_missing_message_key() -> None:
    port = PubSubMessagePort()
    with pytest.raises(MalformedMessageError, match="message"):
        port.decode(RawMessage(payload=b'{"foo": "bar"}'))


def test_decode_rejects_non_string_data() -> None:
    port = PubSubMessagePort()
    with pytest.raises(MalformedMessageError, match="base64"):
        port.decode(RawMessage(payload=b'{"message": {"data": 123}}'))


def test_decode_rejects_invalid_base64() -> None:
    port = PubSubMessagePort()
    bad = json.dumps({"message": {"data": "###not-base64###"}}).encode("utf-8")
    with pytest.raises(MalformedMessageError, match="base64"):
        port.decode(RawMessage(payload=bad))


def test_decode_rejects_non_utf8_decoded_payload() -> None:
    port = PubSubMessagePort()
    encoded = base64.b64encode(b"\xff\xfe\xfd").decode("ascii")
    bad = json.dumps({"message": {"data": encoded}}).encode("utf-8")
    with pytest.raises(MalformedMessageError, match="UTF-8 JSON"):
        port.decode(RawMessage(payload=bad))


def test_decode_rejects_non_object_decoded_payload() -> None:
    port = PubSubMessagePort()
    encoded = base64.b64encode(b"[1,2,3]").decode("ascii")
    bad = json.dumps({"message": {"data": encoded}}).encode("utf-8")
    with pytest.raises(MalformedMessageError, match="JSON object"):
        port.decode(RawMessage(payload=bad))


def test_decode_rejects_invalid_utf8_in_envelope() -> None:
    port = PubSubMessagePort()
    with pytest.raises(MalformedMessageError, match="UTF-8 JSON"):
        port.decode(RawMessage(payload=b"\xff\xfe garbled"))
