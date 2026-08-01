"""DataProvenance separates what was removed, what was missing, and what was assumed."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.readout.data import (
    DataProvenance,
    EntitySummary,
    PeriodCovered,
)


def _provenance(**overrides: object) -> DataProvenance:
    payload: dict[str, object] = {
        "observation_count": 142500,
        "granularity": "transaction",
        "period_covered": PeriodCovered(start=date(2026, 1, 1), end=date(2026, 6, 30)),
        "entities": (EntitySummary(label="SKU", count=8200),),
        "filters_applied": ("Cestas com menos de 3 itens foram descartadas",),
        "known_gaps": ("Semanas 12-14 ausentes na origem",),
        "quality_flags": ("Margem não informada; usado o default de 20%",),
    }
    payload.update(overrides)
    return DataProvenance(**payload)  # type: ignore[arg-type]


def test_complete_provenance_validates() -> None:
    assert _provenance().observation_count == 142500


def test_period_end_must_not_precede_start() -> None:
    with pytest.raises(ValidationError, match="precedes"):
        PeriodCovered(start=date(2026, 6, 30), end=date(2026, 1, 1))


def test_period_may_be_a_single_day() -> None:
    same = date(2026, 6, 30)
    assert PeriodCovered(start=same, end=same).start == same


def test_period_covered_is_optional() -> None:
    """A service with no timestamp column still produces a valid readout."""
    assert _provenance(period_covered=None).period_covered is None


def test_observation_count_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        _provenance(observation_count=0)


def test_entities_are_mandatory() -> None:
    with pytest.raises(ValidationError):
        _provenance(entities=())


def test_the_three_note_lists_may_each_be_empty() -> None:
    clean = _provenance(filters_applied=(), known_gaps=(), quality_flags=())
    assert clean.quality_flags == ()


def test_provenance_is_frozen() -> None:
    provenance = _provenance()
    with pytest.raises(ValidationError):
        provenance.observation_count = 1  # type: ignore[misc]
