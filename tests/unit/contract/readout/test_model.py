"""ModelDescription carries method, not just name."""

from __future__ import annotations

import json

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


@pytest.mark.parametrize(
    "invalid_value",
    [
        pytest.param([1, 2, 3], id="list"),
        pytest.param({"nested": 1}, id="nested_dict"),
        pytest.param((1, 2, 3), id="tuple"),
    ],
)
def test_hyperparameters_reject_collections(invalid_value: object) -> None:
    """Any collection here would be raw data smuggled into the readout."""
    with pytest.raises(ValidationError):
        _model(hyperparameters={"samples": invalid_value})


def test_hyperparameters_accept_bool_int_float_str_and_none() -> None:
    """Exact type must survive validation: True must not become 1, nor 1 become 1.0."""
    model = _model(
        hyperparameters={"level": "both", "top_n": 20, "rate": 0.1, "flag": True, "window": None}
    )
    assert type(model.hyperparameters["level"]) is str
    assert type(model.hyperparameters["top_n"]) is int
    assert type(model.hyperparameters["rate"]) is float
    assert type(model.hyperparameters["flag"]) is bool
    assert model.hyperparameters["window"] is None


def _model_json_payload(hyperparameters: dict[str, object]) -> str:
    payload = {
        "display_name": "Regras de associação por FP-Growth",
        "family": "association_rules",
        "paradigm": "heuristic",
        "objective": "Encontrar produtos comprados juntos mais que o acaso.",
        "formulation": None,
        "assumptions": [
            {
                "statement": "Cada transaction_id representa uma cesta única.",
                "violation_impact": "Cestas fragmentadas inflam o suporte artificialmente.",
                "checked": True,
            }
        ],
        "hyperparameters": hyperparameters,
        "priors": [],
        "not_designed_for": ["inferir causalidade entre os itens da regra"],
    }
    return json.dumps(payload)


def test_hyperparameters_survive_json_round_trip() -> None:
    """The Django platform sends JSON; types must arrive faithful on the other side."""
    raw = _model_json_payload({"min_support": 0.005, "top_n": 20, "level": "both"})
    model = ModelDescription.model_validate_json(raw)
    assert type(model.hyperparameters["min_support"]) is float
    assert type(model.hyperparameters["top_n"]) is int
    assert type(model.hyperparameters["level"]) is str


def test_model_is_frozen() -> None:
    model = _model()
    with pytest.raises(ValidationError):
        model.display_name = "outro"  # type: ignore[misc]


def test_prior_requires_rationale() -> None:
    with pytest.raises(ValidationError):
        Prior(parameter="alpha", distribution="Beta(1,1)", rationale="")


def test_not_designed_for_rejects_an_oversized_single_item() -> None:
    """A tuple's own max_length bounds item *count*, never item *length*."""
    with pytest.raises(ValidationError):
        _model(not_designed_for=("x" * 2_000_000,))


def test_hyperparameters_reject_an_oversized_string_value() -> None:
    """StrictStr alone has no length bound -- a megabyte-scale string like
    a serialized posterior sample would otherwise validate as one scalar."""
    with pytest.raises(ValidationError):
        _model(hyperparameters={"posterior_samples": "x" * 2_000_000})


def test_hyperparameters_reject_an_oversized_key() -> None:
    with pytest.raises(ValidationError):
        _model(hyperparameters={"x" * 200: 1})
