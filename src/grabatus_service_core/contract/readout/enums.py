"""Closed vocabularies used across the readout models."""

from __future__ import annotations

from typing import Final, Literal

from grabatus_service_core.contract.io_spec import ROLE_PATTERN

# Only ROLE_PATTERN needs an explicit reexport marker: it is imported here
# from io_spec rather than defined, so without this, lint sees an "unused"
# import even though every other readout module imports it from this file.
__all__ = ["ROLE_PATTERN"]

READOUT_OUTPUT_ROLE: Final[str] = "model_readout"

# No `Final[str]` here on purpose: an explicit `str` annotation would widen
# the constant and make `readout_version: Literal["1.0"] = READOUT_VERSION`
# in root.py fail mypy --strict (Literal["1.0"] cannot default to a bare
# str). Leaving the annotation off lets mypy infer the narrower
# Literal["1.0"] from the string literal on the right-hand side.
READOUT_VERSION: Final = "1.0"

# Shared by every readout model that bounds a collection. Defined once
# here rather than duplicated per module.
MAX_ITEMS: Final[int] = 30

# Bounds a single string item inside a `tuple[str, ...]` field. Every note
# list across the readout (data.py's three provenance notes, knowledge.py's
# usage/limitation bullets, model.py's not_designed_for) is the same shape
# of content: one short, human-written line — never a place for raw data.
ITEM_MAX_LENGTH: Final[int] = 300

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
