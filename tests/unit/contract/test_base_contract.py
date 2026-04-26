"""Tests for BaseServiceContract (generic over the parameters type)."""

from __future__ import annotations

from typing import Literal

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from grabatus_service_core.contract import BaseServiceContract


class _SampleParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    period: int = 30
    mode: Literal["fast", "slow"] = "fast"


def _valid_payload() -> dict[str, object]:
    return {
        "envelope": {
            "protocol_version": "1.0",
            "request_id": "a3f9c21e-bf38-4e75-9a2f-c89b6c3f2d12",
            "created_at": "2026-04-25T14:32:10Z",
            "origin": "web",
        },
        "identity": {"user_id": "999", "tenant_id": "grabatus"},
        "references": {"parameter_id": "p-1", "result_id": "r-1"},
        "service": {"name": "sample", "version": "1.0.0"},
        "inputs": [
            {
                "role": "timeseries",
                "source_uri": "gs://bucket/in.xlsx",
                "format": "xlsx",
                "format_hints": {"format": "xlsx", "sheet": "Dados"},
            },
        ],
        "outputs": [
            {
                "role": "result_json",
                "destination_uri": "gs://bucket/out.json",
                "format": "json",
                "format_hints": {"format": "json"},
            },
        ],
        "callback": {
            "url": "https://grabatus.com/webhook",
            "auth_scheme": "jwt_hs256",
        },
        "parameters": {"period": 60, "mode": "slow"},
    }


def test_base_contract_accepts_full_valid_payload() -> None:
    contract = BaseServiceContract[_SampleParameters].model_validate(_valid_payload())

    assert contract.envelope.protocol_version == "1.0"
    assert contract.identity.tenant_id == "grabatus"
    assert len(contract.inputs) == 1
    assert len(contract.outputs) == 1
    assert isinstance(contract.parameters, _SampleParameters)
    assert contract.parameters.period == 60


def test_base_contract_requires_at_least_one_input() -> None:
    payload = _valid_payload() | {"inputs": []}

    with pytest.raises(ValidationError, match="inputs"):
        BaseServiceContract[_SampleParameters].model_validate(payload)


def test_base_contract_requires_at_least_one_output() -> None:
    payload = _valid_payload() | {"outputs": []}

    with pytest.raises(ValidationError, match="outputs"):
        BaseServiceContract[_SampleParameters].model_validate(payload)


def test_base_contract_caps_input_count_at_ten() -> None:
    one_input = _valid_payload()["inputs"][0]  # type: ignore[index]
    payload = _valid_payload() | {"inputs": [one_input] * 11}

    with pytest.raises(ValidationError, match="inputs"):
        BaseServiceContract[_SampleParameters].model_validate(payload)


def test_base_contract_rejects_duplicate_input_roles() -> None:
    one_input = _valid_payload()["inputs"][0]  # type: ignore[index]
    payload = _valid_payload() | {"inputs": [one_input, one_input]}

    with pytest.raises(ValidationError, match="role"):
        BaseServiceContract[_SampleParameters].model_validate(payload)


def test_base_contract_rejects_duplicate_output_roles() -> None:
    one_output = _valid_payload()["outputs"][0]  # type: ignore[index]
    payload = _valid_payload() | {"outputs": [one_output, one_output]}

    with pytest.raises(ValidationError, match="role"):
        BaseServiceContract[_SampleParameters].model_validate(payload)


def test_base_contract_propagates_parameters_validation() -> None:
    payload = _valid_payload() | {"parameters": {"mode": "turbo"}}

    with pytest.raises(ValidationError, match="mode"):
        BaseServiceContract[_SampleParameters].model_validate(payload)


def test_base_contract_is_frozen() -> None:
    contract = BaseServiceContract[_SampleParameters].model_validate(_valid_payload())

    with pytest.raises(ValidationError, match="frozen"):
        contract.parameters = _SampleParameters()  # type: ignore[misc]


def test_base_contract_rejects_unsupported_protocol_version() -> None:
    payload = _valid_payload()
    payload_envelope = dict(payload["envelope"])  # type: ignore[arg-type]
    payload_envelope["protocol_version"] = "0.9"
    payload = payload | {"envelope": payload_envelope}

    with pytest.raises(ValidationError, match="protocol_version"):
        BaseServiceContract[_SampleParameters].model_validate(payload)
