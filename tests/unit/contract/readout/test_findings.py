"""Findings are structured so the LLM narrates instead of computing."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.readout.findings import (
    ComparisonBaseline,
    Finding,
    Quantity,
    Uncertainty,
)

if TYPE_CHECKING:
    from grabatus_service_core.contract.readout.enums import UncertaintyKind

_INTERVAL_KINDS: tuple[UncertaintyKind, ...] = (
    "credible_interval",
    "confidence_interval",
    "prediction_interval",
)


def _finding(**overrides: object) -> Finding:
    payload: dict[str, object] = {
        "id": "rule_001",
        "importance": 1,
        "statement": "Quem leva vinho premium leva queijo importado em 73% das cestas.",
        "quantity": Quantity(value=18500.0, unit="BRL"),
        "uncertainty": Uncertainty(kind="none", level=None, lower=None, upper=None),
        "direction": "increase",
        "comparison_baseline": ComparisonBaseline(label="cestas sem a ação", value=0.0),
        "confidence": "high",
        "confidence_rationale": "Baseado em 1.730 cestas observadas.",
    }
    payload.update(overrides)
    return Finding(**payload)  # type: ignore[arg-type]


def test_complete_finding_validates() -> None:
    assert _finding().id == "rule_001"


def test_id_follows_a_referenceable_pattern() -> None:
    """`recommended_narrative_order` points at these ids."""
    with pytest.raises(ValidationError):
        _finding(id="rule 001")


def test_importance_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        _finding(importance=0)


@pytest.mark.parametrize("kind", _INTERVAL_KINDS)
def test_interval_requires_both_bounds(kind: UncertaintyKind) -> None:
    with pytest.raises(ValidationError, match="lower and upper"):
        Uncertainty(kind=kind, level=0.9, lower=41100.0, upper=None)


@pytest.mark.parametrize("kind", _INTERVAL_KINDS)
def test_interval_requires_a_level(kind: UncertaintyKind) -> None:
    with pytest.raises(ValidationError, match="requires a level"):
        Uncertainty(kind=kind, level=None, lower=41100.0, upper=56800.0)


@pytest.mark.parametrize("kind", _INTERVAL_KINDS)
def test_interval_upper_must_not_precede_lower(kind: UncertaintyKind) -> None:
    with pytest.raises(ValidationError, match="precedes"):
        Uncertainty(kind=kind, level=0.9, lower=56800.0, upper=41100.0)


@pytest.mark.parametrize("kind", _INTERVAL_KINDS)
def test_interval_accepts_equal_bounds(kind: UncertaintyKind) -> None:
    """upper == lower is a degenerate but not fabricated interval."""
    interval = Uncertainty(kind=kind, level=0.9, lower=100.0, upper=100.0)
    assert interval.upper == interval.lower


def test_kind_none_forbids_bounds() -> None:
    """A deterministic result claiming an interval would be a fabricated one."""
    with pytest.raises(ValidationError, match="forbids bounds"):
        Uncertainty(kind="none", level=None, lower=1.0, upper=2.0)


def test_kind_none_forbids_lower_alone() -> None:
    """Only one bound set is still a fabricated interval, not a harmless partial one."""
    with pytest.raises(ValidationError, match="forbids bounds"):
        Uncertainty(kind="none", level=None, lower=1.0, upper=None)


def test_kind_none_forbids_upper_alone() -> None:
    with pytest.raises(ValidationError, match="forbids bounds"):
        Uncertainty(kind="none", level=None, lower=None, upper=2.0)


def test_kind_none_is_valid_without_bounds() -> None:
    uncertainty = Uncertainty(kind="none", level=None, lower=None, upper=None)
    assert uncertainty.kind == "none"
    assert uncertainty.lower is None
    assert uncertainty.upper is None


def test_standard_error_needs_no_bounds() -> None:
    error = Uncertainty(kind="standard_error", level=None, lower=None, upper=None)
    assert error.kind == "standard_error"


def test_standard_error_permits_bounds_without_a_level() -> None:
    """standard_error neither requires nor forbids bounds -- unlike the interval
    kinds (which need a level too) and unlike `none` (which forbids them)."""
    error = Uncertainty(kind="standard_error", level=None, lower=41100.0, upper=56800.0)
    assert error.lower == 41100.0
    assert error.upper == 56800.0


def test_comparison_baseline_is_optional() -> None:
    assert _finding(comparison_baseline=None).comparison_baseline is None


def test_confidence_rationale_is_mandatory() -> None:
    """A confidence level with no reason is an opinion wearing a number."""
    with pytest.raises(ValidationError):
        _finding(confidence_rationale="")


def test_confidence_rationale_cannot_be_omitted() -> None:
    """Pydantic v2 does not revalidate a field's default on omission, so an
    empty-string check alone would not catch the field quietly becoming
    optional -- only dropping the key entirely proves it is still required."""
    payload: dict[str, object] = {
        "id": "rule_001",
        "importance": 1,
        "statement": "Quem leva vinho premium leva queijo importado em 73% das cestas.",
        "quantity": Quantity(value=18500.0, unit="BRL"),
        "uncertainty": Uncertainty(kind="none", level=None, lower=None, upper=None),
        "direction": "increase",
        "comparison_baseline": None,
        "confidence": "high",
    }
    with pytest.raises(ValidationError):
        Finding(**payload)  # type: ignore[arg-type]


def test_finding_is_frozen() -> None:
    finding = _finding()
    with pytest.raises(ValidationError):
        finding.statement = "outro"  # type: ignore[misc]


def test_finding_forbids_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        _finding(nao_existe="valor")


def test_uncertainty_forbids_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Uncertainty(
            kind="none",
            level=None,
            lower=None,
            upper=None,
            extra_field="valor",  # type: ignore[call-arg]
        )
