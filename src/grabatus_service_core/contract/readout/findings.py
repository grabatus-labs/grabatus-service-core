"""Finding: one conclusion, with its size and its uncertainty kept apart.

Value, unit, uncertainty and baseline are separate fields so the LLM
narrates them. It does not compute, round, or compare on its own.
"""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from grabatus_service_core.contract.readout.enums import (
    Confidence,
    Direction,
    UncertaintyKind,
)

_FROZEN = ConfigDict(extra="forbid", frozen=True)

_ID_PATTERN = r"^[a-z][a-z0-9_]*$"
_INTERVAL_KINDS = frozenset({"credible_interval", "confidence_interval", "prediction_interval"})


class Quantity(BaseModel):
    """The number itself, with its unit."""

    model_config = _FROZEN

    value: float
    unit: str = Field(min_length=1, max_length=64)


class Uncertainty(BaseModel):
    """How sure the number is, in the vocabulary of the method used."""

    model_config = _FROZEN

    kind: UncertaintyKind
    level: float | None = Field(default=None, gt=0.0, lt=1.0)
    lower: float | None = None
    upper: float | None = None

    @model_validator(mode="after")
    def _bounds_match_the_kind(self) -> Self:
        if self.kind in _INTERVAL_KINDS:
            return self._validated_interval()
        if self.kind == "none" and (self.lower is not None or self.upper is not None):
            raise ValueError(
                f"kind='none' forbids bounds, got lower={self.lower!r}, upper={self.upper!r}"
            )
        return self

    def _validated_interval(self) -> Self:
        if self.level is None:
            raise ValueError(f"kind={self.kind!r} requires a level, got None")
        if self.lower is None or self.upper is None:
            raise ValueError(
                f"kind={self.kind!r} requires lower and upper, "
                f"got lower={self.lower!r}, upper={self.upper!r}"
            )
        if self.upper < self.lower:
            raise ValueError(f"upper={self.upper!r} precedes lower={self.lower!r}")
        return self


class ComparisonBaseline(BaseModel):
    """What the finding is being compared against."""

    model_config = _FROZEN

    label: str = Field(min_length=1, max_length=200)
    value: float


class Finding(BaseModel):
    """One conclusion the service is willing to stand behind."""

    model_config = _FROZEN

    id: str = Field(min_length=1, max_length=64, pattern=_ID_PATTERN)
    importance: int = Field(ge=1, le=100)
    statement: str = Field(min_length=1, max_length=1000)
    quantity: Quantity
    uncertainty: Uncertainty
    direction: Direction
    comparison_baseline: ComparisonBaseline | None = None
    confidence: Confidence
    confidence_rationale: str = Field(min_length=1, max_length=500)
