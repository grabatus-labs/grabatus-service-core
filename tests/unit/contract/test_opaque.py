"""Verify OpaqueServiceContract validates envelope/I-O but not parameters shape."""

import json
from typing import Any

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.opaque import (
    OpaqueParameters,
    OpaqueServiceContract,
)
from grabatus_service_core.testing.factories import (
    make_callback,
    make_envelope,
    make_identity,
    make_input_spec,
    make_output_spec,
    make_references,
    make_service_descriptor,
)


def _build_payload(parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        "envelope": json.loads(make_envelope().model_dump_json()),
        "identity": json.loads(make_identity().model_dump_json()),
        "references": json.loads(make_references().model_dump_json()),
        "service": json.loads(make_service_descriptor().model_dump_json()),
        "inputs": [json.loads(make_input_spec().model_dump_json())],
        "outputs": [json.loads(make_output_spec().model_dump_json())],
        "callback": json.loads(make_callback().model_dump_json()),
        "parameters": parameters,
    }


def test_opaque_contract_accepts_arbitrary_parameters_dict() -> None:
    payload = _build_payload({"anything": 1, "even_nested": {"and": ["arrays"]}})
    contract = OpaqueServiceContract.model_validate(payload)
    assert contract.parameters.model_dump()["anything"] == 1


def test_opaque_contract_accepts_empty_parameters_dict() -> None:
    payload = _build_payload({})
    contract = OpaqueServiceContract.model_validate(payload)
    assert contract.parameters.model_dump() == {}


def test_opaque_contract_still_rejects_missing_envelope() -> None:
    payload = _build_payload({"x": 1})
    del payload["envelope"]
    with pytest.raises(ValidationError, match=r"envelope"):
        OpaqueServiceContract.model_validate(payload)


def test_opaque_contract_still_rejects_zero_inputs() -> None:
    payload = _build_payload({"x": 1})
    payload["inputs"] = []
    with pytest.raises(ValidationError, match=r"at least 1"):
        OpaqueServiceContract.model_validate(payload)


def test_opaque_parameters_round_trips_unknown_fields() -> None:
    params = OpaqueParameters.model_validate({"foo": "bar", "n": 42})
    dumped = params.model_dump()
    assert dumped == {"foo": "bar", "n": 42}


def test_opaque_parameters_is_frozen() -> None:
    params = OpaqueParameters.model_validate({"x": 1})
    with pytest.raises(ValidationError):
        params.x = 2  # type: ignore[attr-defined]
