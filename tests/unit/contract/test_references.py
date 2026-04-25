"""Tests for the References schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.references import References


def test_references_accepts_valid_ids() -> None:
    refs = References.model_validate(
        {"parameter_id": "param-001", "result_id": "result-001"},
    )

    assert refs.parameter_id == "param-001"
    assert refs.result_id == "result-001"


def test_references_rejects_empty_parameter_id() -> None:
    with pytest.raises(ValidationError, match="parameter_id"):
        References.model_validate({"parameter_id": "", "result_id": "r-1"})


def test_references_rejects_empty_result_id() -> None:
    with pytest.raises(ValidationError, match="result_id"):
        References.model_validate({"parameter_id": "p-1", "result_id": ""})


def test_references_is_frozen() -> None:
    refs = References.model_validate({"parameter_id": "p", "result_id": "r"})

    with pytest.raises(ValidationError, match="frozen"):
        refs.parameter_id = "x"  # type: ignore[misc]


def test_references_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError, match="extra"):
        References.model_validate(
            {"parameter_id": "p", "result_id": "r", "other": "x"},
        )
