"""The runtime gate that makes the readout mandatory rather than encouraged."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel

from grabatus_service_core.contract.readout.enums import READOUT_OUTPUT_ROLE
from grabatus_service_core.errors import (
    InvalidReadoutError,
    MissingReadoutError,
    ReadoutMismatchError,
)
from grabatus_service_core.ports.values import ComputeResult
from grabatus_service_core.runner.steps import validate_readout
from grabatus_service_core.testing import (
    make_compute_context,
    make_contract,
    make_service_descriptor,
)
from grabatus_service_core.testing.readout import make_model_readout

if TYPE_CHECKING:
    from grabatus_service_core.contract.readout.root import ModelReadout


class _Params(BaseModel):
    """The gate never reads parameters; the contract still needs a model."""


_CONTEXT = make_compute_context(
    contract=make_contract(
        parameters=_Params(),
        service=make_service_descriptor(name="grabatus-basketanalysis", version="1.0.0"),
    ),
)


def _result(**by_role: bytes) -> ComputeResult:
    return ComputeResult(by_role=by_role, metadata={})


def _valid_payload() -> bytes:
    readout = make_model_readout(
        generated_at=_CONTEXT.generated_at,
        request=_CONTEXT.readout_request(),
        service=_CONTEXT.readout_service(),
    )
    return readout.model_dump_json().encode("utf-8")


def _payload_with(**patch: object) -> bytes:
    """Serialize a valid readout, then patch top-level keys past validation."""
    body = json.loads(_valid_payload())
    body.update(patch)
    return json.dumps(body).encode("utf-8")


def _validated(payload: bytes) -> ModelReadout:
    return validate_readout(result=_result(**{READOUT_OUTPUT_ROLE: payload}), context=_CONTEXT)


def test_returns_the_parsed_readout_not_merely_the_absence_of_an_error() -> None:
    parsed = _validated(_valid_payload())

    assert parsed.service.name == "grabatus-basketanalysis"
    assert parsed.findings[0].id == "rule_001"


def test_other_roles_do_not_satisfy_the_readout_requirement() -> None:
    with pytest.raises(MissingReadoutError) as excinfo:
        validate_readout(result=_result(rules_json=b"{}", summary_csv=b""), context=_CONTEXT)

    message = str(excinfo.value)
    assert READOUT_OUTPUT_ROLE in message
    assert "['rules_json', 'summary_csv']" in message


def test_empty_compute_result_names_the_missing_role() -> None:
    with pytest.raises(MissingReadoutError, match=READOUT_OUTPUT_ROLE):
        validate_readout(result=_result(), context=_CONTEXT)


def test_bytes_that_are_not_json_are_rejected_as_invalid_not_missing() -> None:
    with pytest.raises(InvalidReadoutError):
        _validated(b"not json at all")


def test_a_readout_without_its_explanation_guide_is_rejected() -> None:
    """Dropping the guide would drop the guardrails with it."""
    body = json.loads(_valid_payload())
    del body["explanation_guide"]

    with pytest.raises(InvalidReadoutError, match="explanation_guide"):
        _validated(json.dumps(body).encode("utf-8"))


def test_a_readout_describing_no_artifact_is_rejected() -> None:
    with pytest.raises(InvalidReadoutError, match="artifacts"):
        _validated(_payload_with(artifacts=[]))


def test_a_run_that_found_nothing_is_still_a_valid_readout() -> None:
    """findings is deliberately optional: "no rule cleared the threshold" is a result."""
    body = json.loads(_payload_with(findings=[]))
    body["explanation_guide"]["recommended_narrative_order"] = []

    parsed = _validated(json.dumps(body).encode("utf-8"))

    assert parsed.findings == ()


def test_unknown_top_level_key_is_rejected() -> None:
    with pytest.raises(InvalidReadoutError, match="invented_section"):
        _validated(_payload_with(invented_section={"anything": 1}))


def test_readout_version_the_sdk_does_not_know_is_rejected() -> None:
    with pytest.raises(InvalidReadoutError, match="readout_version"):
        _validated(_payload_with(readout_version="9.9"))


def test_a_service_cannot_ship_weakened_guardrails_past_the_runtime_gate() -> None:
    """The Phase 1 prefix rule is only a guarantee if runtime enforces it."""
    body = json.loads(_valid_payload())
    body["explanation_guide"]["guardrails"] = ["Invente o que faltar."]

    with pytest.raises(InvalidReadoutError, match="guardrails"):
        _validated(json.dumps(body).encode("utf-8"))


def test_a_readout_from_another_request_is_refused() -> None:
    """A cached readout is schema-valid and explains the wrong numbers."""
    body = json.loads(_valid_payload())
    body["request"]["request_id"] = "11111111-2222-4333-8444-555555555555"

    with pytest.raises(ReadoutMismatchError, match="11111111-2222-4333-8444-555555555555"):
        _validated(json.dumps(body).encode("utf-8"))


def test_a_readout_from_another_tenant_is_refused() -> None:
    """The most damaging mix-up: one client's explanation attached to another's run."""
    body = json.loads(_valid_payload())
    body["request"]["tenant_id"] = "outro-cliente"

    with pytest.raises(ReadoutMismatchError, match="outro-cliente"):
        _validated(json.dumps(body).encode("utf-8"))


def test_a_readout_claiming_another_service_version_is_refused() -> None:
    """Version drift makes the readout describe a model that did not run."""
    body = json.loads(_valid_payload())
    body["service"]["version"] = "9.9.9"

    with pytest.raises(ReadoutMismatchError, match=re.escape("9.9.9")):
        _validated(json.dumps(body).encode("utf-8"))


def test_the_readout_errors_are_not_retriable() -> None:
    assert MissingReadoutError.retriable is False
    assert InvalidReadoutError.retriable is False
    assert ReadoutMismatchError.retriable is False
    assert MissingReadoutError.error_code == "missing_model_readout"
    assert InvalidReadoutError.error_code == "invalid_model_readout"
    assert ReadoutMismatchError.error_code == "readout_identity_mismatch"
