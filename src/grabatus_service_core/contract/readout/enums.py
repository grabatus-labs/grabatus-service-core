"""Closed vocabularies used across the readout models."""

from __future__ import annotations

from typing import Final, Literal

from grabatus_service_core.contract.io_spec import ROLE_PATTERN

# Only ROLE_PATTERN needs an explicit reexport marker: it is imported here
# from io_spec rather than defined, so without this, lint sees an "unused"
# import even though every other readout module imports it from this file.
__all__ = ["ROLE_PATTERN"]

READOUT_OUTPUT_ROLE: Final[str] = "model_readout"
READOUT_VERSION: Final[str] = "1.0"

# Shared by every readout model that bounds a collection. Defined once
# here rather than duplicated per module.
MAX_ITEMS: Final[int] = 30

ModelFamily = Literal[
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
]

Paradigm = Literal[
    "bayesian",
    "frequentist",
    "optimization",
    "heuristic",
    "ml_supervised",
    "ml_unsupervised",
]

UncertaintyKind = Literal[
    "credible_interval",
    "confidence_interval",
    "prediction_interval",
    "standard_error",
    "none",
]

Direction = Literal["increase", "decrease", "stable", "not_applicable"]
Confidence = Literal["high", "moderate", "low"]
DiagnosticStatus = Literal["pass", "warn", "fail"]
QualityStatus = Literal["pass", "warn", "fail"]
Severity = Literal["high", "medium", "low"]
