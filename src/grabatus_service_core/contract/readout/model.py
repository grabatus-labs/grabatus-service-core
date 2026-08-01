"""ModelDescription: the method behind the numbers."""

from __future__ import annotations

from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    Strict,
    StrictBool,
    StrictFloat,
    StrictInt,
    StringConstraints,
)

from grabatus_service_core.contract.readout.enums import (
    ITEM_MAX_LENGTH,
    MAX_ITEMS,
    ModelFamily,
    Paradigm,
)

_FROZEN = ConfigDict(extra="forbid", frozen=True)

_MAX_HYPERPARAMETERS = 50

# Hyperparameter names are short identifiers, not prose — the same bound
# Prior.parameter uses below.
_MAX_HYPERPARAMETER_NAME_LENGTH = 120

# Scalars only, and Strict*: accepting a collection here would let raw data
# into the readout through the side door (spec §4.3), and a lax union would
# let Pydantic coerce bool->int->float->str by union order, silently
# changing the value's type. The string arm additionally bounds length —
# StrictStr alone has no length limit, so an unbounded string is exactly as
# good a side door for raw data as a collection would have been (e.g.
# {"posterior_samples": "<1.9 MB string>"} validated before this bound).
_StrictBoundedStr = Annotated[str, Strict(), StringConstraints(max_length=ITEM_MAX_LENGTH)]
HyperparameterValue = StrictBool | StrictInt | StrictFloat | _StrictBoundedStr | None

# Bounds the hyperparameter *name*, mirroring the value bound above — an
# unbounded dict key is the same side door as an unbounded value.
_HyperparameterName = Annotated[str, StringConstraints(max_length=_MAX_HYPERPARAMETER_NAME_LENGTH)]

# Each item is one short capability statement — not a place to smuggle a
# large payload as a single tuple item.
_Capability = Annotated[str, StringConstraints(max_length=ITEM_MAX_LENGTH)]


class Assumption(BaseModel):
    """A stated assumption, with the cost of it being wrong."""

    model_config = _FROZEN

    statement: str = Field(min_length=1, max_length=500)
    violation_impact: str = Field(min_length=1, max_length=500)
    checked: bool


class Prior(BaseModel):
    """A prior distribution and why it was chosen."""

    model_config = _FROZEN

    parameter: str = Field(min_length=1, max_length=120)
    distribution: str = Field(min_length=1, max_length=200)
    rationale: str = Field(min_length=1, max_length=500)


class ModelDescription(BaseModel):
    """What was fitted, under what assumptions, and what it cannot answer."""

    model_config = _FROZEN

    display_name: str = Field(min_length=1, max_length=200)
    family: ModelFamily
    paradigm: Paradigm
    objective: str = Field(min_length=1, max_length=1000)
    formulation: str | None = Field(default=None, max_length=500)
    assumptions: tuple[Assumption, ...] = Field(min_length=1, max_length=MAX_ITEMS)
    hyperparameters: dict[_HyperparameterName, HyperparameterValue] = Field(
        max_length=_MAX_HYPERPARAMETERS
    )
    priors: tuple[Prior, ...] = Field(default=(), max_length=MAX_ITEMS)
    not_designed_for: tuple[_Capability, ...] = Field(min_length=1, max_length=MAX_ITEMS)
