"""Tests for the InputSpec schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.io_spec import InputSpec
from grabatus_service_core.contract.secret_ref import SecretRef


def _valid_input() -> dict[str, object]:
    return {
        "role": "timeseries",
        "source_uri": "gs://bucket/path/file.xlsx",
        "format": "xlsx",
        "format_hints": {"format": "xlsx", "sheet": "Dados", "header": 0},
    }


def test_input_spec_accepts_minimal_valid_payload() -> None:
    spec = InputSpec.model_validate(_valid_input())

    assert spec.role == "timeseries"
    assert str(spec.source_uri) == "gs://bucket/path/file.xlsx"
    assert spec.format == "xlsx"
    assert spec.credential_ref is None


def test_input_spec_accepts_credential_ref_uri() -> None:
    payload = _valid_input() | {"credential_ref": "secret://gsm/bq-reader/1"}

    spec = InputSpec.model_validate(payload)

    assert isinstance(spec.credential_ref, SecretRef)
    assert spec.credential_ref.name == "bq-reader"


@pytest.mark.parametrize(
    "role",
    ["Timeseries", "time-series", "time series", "1timeseries", ""],
)
def test_input_spec_rejects_invalid_roles(role: str) -> None:
    payload = _valid_input() | {"role": role}

    with pytest.raises(ValidationError, match="role"):
        InputSpec.model_validate(payload)


@pytest.mark.parametrize(
    "role",
    ["timeseries", "holidays", "training_data", "auxiliary_features"],
)
def test_input_spec_accepts_valid_roles(role: str) -> None:
    payload = _valid_input() | {"role": role}

    spec = InputSpec.model_validate(payload)

    assert spec.role == role


def test_input_spec_rejects_format_hint_mismatch() -> None:
    payload = _valid_input() | {
        "format": "csv",
        "format_hints": {"format": "xlsx", "sheet": "X"},
    }

    with pytest.raises(ValidationError, match="format"):
        InputSpec.model_validate(payload)


def test_input_spec_is_frozen() -> None:
    spec = InputSpec.model_validate(_valid_input())

    with pytest.raises(ValidationError, match="frozen"):
        spec.role = "other"  # type: ignore[misc]


def test_input_spec_rejects_extra_fields() -> None:
    payload = _valid_input() | {"unknown": "x"}

    with pytest.raises(ValidationError, match="extra"):
        InputSpec.model_validate(payload)
