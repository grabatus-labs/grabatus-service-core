"""Tests for runner state dataclasses."""

from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import BaseModel

from grabatus_service_core.errors import ComputeError
from grabatus_service_core.ports.values import (
    Credentials,
    WebhookAck,
    WriteReceipt,
)
from grabatus_service_core.runner.state import (
    AuthorizedContract,
    CredentialBundle,
    ExecutionResult,
    ParsedEnvelope,
    ValidatedContract,
    WriteReceipts,
)
from grabatus_service_core.testing import make_contract


class _Params(BaseModel):
    horizon: int = 30


def _credentials(token: bytes = b"x") -> Credentials:
    return Credentials(token=token, token_type="bearer")


def _write_receipt() -> WriteReceipt:
    return WriteReceipt(
        uri="gs://bucket/key",
        bytes_written=42,
        request_id_tag="rid",
    )


def test_parsed_envelope_freezes_payload_against_mutation() -> None:
    payload = {"a": 1}
    parsed = ParsedEnvelope(payload=payload)

    with pytest.raises(TypeError):
        parsed.payload["b"] = 2  # type: ignore[index]


def test_parsed_envelope_is_immutable() -> None:
    parsed = ParsedEnvelope(payload={"a": 1})

    with pytest.raises((AttributeError, TypeError)):
        parsed.payload = {"b": 2}  # type: ignore[misc]


def test_validated_contract_carries_contract() -> None:
    contract = make_contract(parameters=_Params())

    validated = ValidatedContract(contract=contract)

    assert validated.contract is contract


def test_authorized_contract_carries_contract() -> None:
    contract = make_contract(parameters=_Params())

    authorized = AuthorizedContract(contract=contract)

    assert authorized.contract is contract


def test_credential_bundle_freezes_input_and_output_mappings() -> None:
    bundle = CredentialBundle(
        inputs={"timeseries": _credentials(b"in")},
        outputs={"result_json": _credentials(b"out")},
    )

    with pytest.raises(TypeError):
        bundle.inputs["new"] = _credentials()  # type: ignore[index]
    with pytest.raises(TypeError):
        bundle.outputs["new"] = _credentials()  # type: ignore[index]


def test_write_receipts_freezes_by_role_mapping() -> None:
    receipts = WriteReceipts(by_role={"result_json": _write_receipt()})

    with pytest.raises(TypeError):
        receipts.by_role["other"] = _write_receipt()  # type: ignore[index]


def test_execution_result_for_success_carries_receipts_and_no_error() -> None:
    contract = make_contract(parameters=_Params())
    rid = UUID("11111111-2222-3333-4444-555555555555")
    receipts = WriteReceipts(by_role={"result_json": _write_receipt()})
    ack = WebhookAck(http_status=200, response_body="ok")

    result = ExecutionResult(
        request_id=rid,
        status="ok",
        contract=contract,
        receipts=receipts,
        error=None,
        metadata={"version": "1.0"},
        webhook_ack=ack,
    )

    assert result.status == "ok"
    assert result.error is None
    assert result.receipts is receipts
    assert result.webhook_ack is ack


def test_execution_result_for_failure_carries_error_and_no_receipts() -> None:
    rid = UUID("11111111-2222-3333-4444-555555555555")
    err = ComputeError("boom")

    result = ExecutionResult(
        request_id=rid,
        status="error",
        contract=None,
        receipts=None,
        error=err,
        metadata={},
        webhook_ack=None,
    )

    assert result.status == "error"
    assert result.error is err
    assert result.receipts is None


def test_execution_result_metadata_is_immutable() -> None:
    result = ExecutionResult(
        request_id=UUID("11111111-2222-3333-4444-555555555555"),
        status="error",
        contract=None,
        receipts=None,
        error=ComputeError("x"),
        metadata={"a": 1},
        webhook_ack=None,
    )

    with pytest.raises(TypeError):
        result.metadata["b"] = 2  # type: ignore[index]
