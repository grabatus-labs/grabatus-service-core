"""Tests for the contract factories used by service tests."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from grabatus_service_core.contract import BaseServiceContract
from grabatus_service_core.testing import (
    make_callback,
    make_contract,
    make_envelope,
    make_identity,
    make_input_spec,
    make_output_spec,
    make_references,
    make_service_descriptor,
)


class _SampleParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    period: int = 30
    mode: Literal["fast", "slow"] = "fast"


def test_make_envelope_returns_valid_envelope() -> None:
    env = make_envelope()

    assert env.protocol_version == "1.0"
    assert isinstance(env.request_id, UUID)


def test_make_envelope_overrides_request_id() -> None:
    rid = UUID("a3f9c21e-bf38-4e75-9a2f-c89b6c3f2d12")

    env = make_envelope(request_id=rid)

    assert env.request_id == rid


def test_make_identity_default() -> None:
    identity = make_identity()

    assert identity.tenant_id == "grabatus"


def test_make_input_spec_default() -> None:
    spec = make_input_spec()

    assert spec.role == "timeseries"
    assert spec.format == "xlsx"


def test_make_output_spec_default() -> None:
    spec = make_output_spec()

    assert spec.role == "result_json"
    assert spec.format == "json"


def test_make_references_default() -> None:
    refs = make_references()

    assert refs.parameter_id
    assert refs.result_id


def test_make_service_descriptor_default() -> None:
    desc = make_service_descriptor()

    assert desc.name == "sample"


def test_make_callback_default_is_https() -> None:
    cb = make_callback()

    assert str(cb.url).startswith("https://")


def test_make_contract_default_is_valid() -> None:
    contract = make_contract(parameters=_SampleParameters())

    assert isinstance(contract, BaseServiceContract)
    assert len(contract.inputs) == 1
    assert len(contract.outputs) == 1


def test_make_contract_accepts_overrides() -> None:
    contract = make_contract(
        parameters=_SampleParameters(period=180, mode="slow"),
        identity=make_identity(tenant_id="other"),
    )

    assert contract.parameters.period == 180
    assert contract.identity.tenant_id == "other"
