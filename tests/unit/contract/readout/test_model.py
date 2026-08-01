"""ModelDescription carries method, not just name."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.readout.model import Assumption, ModelDescription, Prior


def _model(**overrides: object) -> ModelDescription:
    payload: dict[str, object] = {
        "display_name": "Regras de associação por FP-Growth",
        "family": "association_rules",
        "paradigm": "heuristic",
        "objective": "Encontrar produtos comprados juntos mais que o acaso.",
        "formulation": "lift(A→B) = P(B|A) / P(B)",
        "assumptions": (
            Assumption(
                statement="Cada transaction_id representa uma cesta única.",
                violation_impact="Cestas fragmentadas inflam o suporte artificialmente.",
                checked=True,
            ),
        ),
        "hyperparameters": {"min_support": 0.005, "capture_rate": 0.10},
        "priors": (),
        "not_designed_for": ("inferir causalidade entre os itens da regra",),
    }
    payload.update(overrides)
    return ModelDescription(**payload)  # type: ignore[arg-type]


def test_complete_model_validates() -> None:
    assert _model().family == "association_rules"


def test_assumptions_are_mandatory() -> None:
    """A model with no stated assumption is a model nobody can challenge."""
    with pytest.raises(ValidationError):
        _model(assumptions=())


def test_not_designed_for_is_mandatory() -> None:
    with pytest.raises(ValidationError):
        _model(not_designed_for=())


def test_priors_may_be_empty_for_non_bayesian_models() -> None:
    assert _model().priors == ()


def test_formulation_is_optional() -> None:
    assert _model(formulation=None).formulation is None


def test_unknown_family_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _model(family="deep_learning")


def test_hyperparameters_reject_collections() -> None:
    """A nested array here would be raw data smuggled into the readout."""
    with pytest.raises(ValidationError):
        _model(hyperparameters={"samples": [1, 2, 3]})


def test_hyperparameters_accept_bool_int_float_str_and_none() -> None:
    model = _model(
        hyperparameters={"level": "both", "top_n": 20, "rate": 0.1, "flag": True, "window": None}
    )
    assert model.hyperparameters["top_n"] == 20


def test_model_is_frozen() -> None:
    model = _model()
    with pytest.raises(ValidationError):
        model.display_name = "outro"  # type: ignore[misc]


def test_prior_requires_rationale() -> None:
    with pytest.raises(ValidationError):
        Prior(parameter="alpha", distribution="Beta(1,1)", rationale="")
