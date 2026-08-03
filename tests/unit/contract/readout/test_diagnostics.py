"""Diagnostics carry the threshold, not just the number."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.readout.diagnostics import Diagnostic, OverallQuality


def test_diagnostic_states_its_threshold_and_meaning() -> None:
    diagnostic = Diagnostic(
        name="data_quality_score",
        value=0.87,
        threshold="> 0.70",
        status="pass",
        meaning="Proporção de transações retidas e de SKUs com preço e categoria.",
    )
    assert diagnostic.status == "pass"


def test_diagnostic_meaning_is_mandatory_and_cannot_be_empty() -> None:
    """A metric with no stated meaning is a number the LLM will guess about."""
    with pytest.raises(ValidationError):
        Diagnostic(name="r_hat_max", value=1.01, threshold="< 1.01", status="pass", meaning="")


def test_diagnostic_meaning_cannot_be_omitted() -> None:
    """Pydantic v2 does not revalidate a default on omission, so ``meaning``
    must be declared without one — otherwise it silently becomes optional
    even though the string-emptiness test above still passes.
    """
    with pytest.raises(ValidationError):
        Diagnostic(name="r_hat_max", value=1.01, threshold="< 1.01", status="pass")  # type: ignore[call-arg]


def test_diagnostic_threshold_cannot_be_omitted() -> None:
    """A diagnostic without a threshold is a number the LLM judges on its own."""
    with pytest.raises(ValidationError):
        Diagnostic(name="x", value=1.0, status="pass", meaning="m")  # type: ignore[call-arg]


def test_unknown_status_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Diagnostic(name="x", value=1.0, threshold="< 2", status="unknown", meaning="m")  # type: ignore[arg-type]


def test_overall_quality_summarises() -> None:
    quality = OverallQuality(status="warn", summary="Nenhuma regra superou os limiares.")
    assert quality.status == "warn"
    assert quality.summary == "Nenhuma regra superou os limiares."


def test_overall_quality_summary_cannot_be_empty() -> None:
    with pytest.raises(ValidationError):
        OverallQuality(status="warn", summary="")


def test_overall_quality_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        OverallQuality(status="unknown", summary="s")  # type: ignore[arg-type]
