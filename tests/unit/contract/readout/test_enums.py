"""The readout vocabularies are closed sets, pinned here against drift."""

from __future__ import annotations

from typing import get_args

from grabatus_service_core.contract import io_spec
from grabatus_service_core.contract.readout.enums import (
    MAX_ITEMS,
    READOUT_OUTPUT_ROLE,
    READOUT_VERSION,
    ROLE_PATTERN,
    Confidence,
    DiagnosticStatus,
    Direction,
    ModelFamily,
    Paradigm,
    QualityStatus,
    Severity,
    UncertaintyKind,
)


def test_output_role_is_the_fixed_contract_role() -> None:
    assert READOUT_OUTPUT_ROLE == "model_readout"


def test_readout_version_is_pinned() -> None:
    assert READOUT_VERSION == "1.0"


def test_model_family_covers_every_grabatus_service_kind() -> None:
    assert set(get_args(ModelFamily)) == {
        "time_series_forecast",
        "bayesian_inference",
        "ab_test",
        "optimization",
        "classification",
        "regression",
        "clustering",
        "survival_analysis",
        "simulation",
        "association_rules",
    }


def test_paradigm_values() -> None:
    assert set(get_args(Paradigm)) == {
        "bayesian",
        "frequentist",
        "optimization",
        "heuristic",
        "ml_supervised",
        "ml_unsupervised",
    }


def test_uncertainty_kind_includes_none_for_deterministic_results() -> None:
    """Association rules have no interval — the readout must still be expressible."""
    assert "none" in get_args(UncertaintyKind)


def test_direction_values() -> None:
    assert set(get_args(Direction)) == {"increase", "decrease", "stable", "not_applicable"}


def test_confidence_values() -> None:
    assert set(get_args(Confidence)) == {"high", "moderate", "low"}


def test_status_vocabularies_share_the_same_three_levels() -> None:
    assert set(get_args(DiagnosticStatus)) == {"pass", "warn", "fail"}
    assert set(get_args(QualityStatus)) == {"pass", "warn", "fail"}


def test_severity_values() -> None:
    assert set(get_args(Severity)) == {"high", "medium", "low"}


def test_role_pattern_matches_the_contract_role_pattern() -> None:
    """Reexported from io_spec.ROLE_PATTERN, not a second copy of the regex."""
    assert ROLE_PATTERN is io_spec.ROLE_PATTERN


def test_max_items_is_the_shared_collection_bound() -> None:
    assert MAX_ITEMS == 30
