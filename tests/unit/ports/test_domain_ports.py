"""Shape tests for domain Ports (Storage/Message/Webhook/Compute/Secrets/Auth)."""

from __future__ import annotations

from typing import Any

import pytest

from grabatus_service_core.ports.authorization import UriAuthorizationPort
from grabatus_service_core.ports.compute import ComputeBackendPort
from grabatus_service_core.ports.message import MessagePort
from grabatus_service_core.ports.secrets import SecretsPort
from grabatus_service_core.ports.storage import StoragePort
from grabatus_service_core.ports.values import (
    ComputeResult,
    Credentials,
    LoadedInputs,
    RawMessage,
    WebhookAck,
    WriteReceipt,
)
from grabatus_service_core.ports.webhook import WebhookPort


class _OkStorage:
    def read(self, *, spec: Any, credentials: Credentials) -> bytes:
        return b""

    def write(
        self,
        *,
        spec: Any,
        payload: bytes,
        credentials: Credentials,
    ) -> WriteReceipt:
        return WriteReceipt(uri="gs://x/y", bytes_written=0, request_id_tag="r")


class _OkMessage:
    def decode(self, raw: RawMessage) -> dict[str, Any]:
        return {}

    def encode(self, envelope: dict[str, Any]) -> bytes:
        return b""


class _OkWebhook:
    def notify(self, *, callback: Any, payload: dict[str, Any]) -> WebhookAck:
        return WebhookAck(http_status=200, response_body="")


class _OkCompute:
    REQUIRED_INPUT_ROLES: frozenset[str] = frozenset({"timeseries"})
    OPTIONAL_INPUT_ROLES: frozenset[str] = frozenset()
    OUTPUT_ROLES: frozenset[str] = frozenset({"result"})

    def run(self, *, inputs: LoadedInputs, parameters: Any) -> ComputeResult:
        return ComputeResult(by_role={}, metadata={})


class _OkSecrets:
    def resolve(self, *, secret_ref: Any) -> Credentials:
        return Credentials(token=b"", token_type="bearer")


class _OkAuth:
    def authorize(self, *, uri: str, identity: Any) -> None:
        return None


def test_storage_port_accepts_full_implementation() -> None:
    assert isinstance(_OkStorage(), StoragePort)


def test_message_port_accepts_full_implementation() -> None:
    assert isinstance(_OkMessage(), MessagePort)


def test_webhook_port_accepts_full_implementation() -> None:
    assert isinstance(_OkWebhook(), WebhookPort)


def test_compute_port_accepts_full_implementation() -> None:
    assert isinstance(_OkCompute(), ComputeBackendPort)


def test_secrets_port_accepts_full_implementation() -> None:
    assert isinstance(_OkSecrets(), SecretsPort)


def test_uri_authorization_port_accepts_full_implementation() -> None:
    assert isinstance(_OkAuth(), UriAuthorizationPort)


def test_value_objects_are_frozen_dataclasses() -> None:
    receipt = WriteReceipt(uri="gs://x/y", bytes_written=10, request_id_tag="r1")
    ack = WebhookAck(http_status=200, response_body="ok")
    creds = Credentials(token=b"abc", token_type="bearer")
    inputs = LoadedInputs(by_role={"timeseries": b"abc"})
    result = ComputeResult(by_role={"out": b"def"}, metadata={"n": 1})
    raw = RawMessage(payload=b"x")

    for obj in (receipt, ack, creds, inputs, result, raw):
        with pytest.raises((AttributeError, TypeError)):
            obj.__dict__["new_attr"] = "x"  # type: ignore[attr-defined]
