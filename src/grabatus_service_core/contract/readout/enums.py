"""Closed vocabularies used across the readout models."""

from __future__ import annotations

from typing import Final, Literal

READOUT_OUTPUT_ROLE: Final[str] = "model_readout"
READOUT_VERSION: Final[str] = "1.0"

# Shared by every readout model that names a contract role or bounds a
# collection. Defined once here rather than duplicated per module.
ROLE_PATTERN: Final[str] = r"^[a-z][a-z0-9_]*$"
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
