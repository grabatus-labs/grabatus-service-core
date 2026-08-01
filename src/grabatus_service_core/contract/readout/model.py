"""ModelDescription: the method behind the numbers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr

from grabatus_service_core.contract.readout.enums import MAX_ITEMS, ModelFamily, Paradigm

_FROZEN = ConfigDict(extra="forbid", frozen=True)

_MAX_HYPERPARAMETERS = 50

# Scalars only, and Strict*: accepting a collection here would let raw data
# into the readout through the side door (spec §4.3), and a lax union would
# let Pydantic coerce bool->int->float->str by union order, silently
# changing the value's type.
HyperparameterValue = StrictBool | StrictInt | StrictFloat | StrictStr | None


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
    hyperparameters: dict[str, HyperparameterValue] = Field(max_length=_MAX_HYPERPARAMETERS)
    priors: tuple[Prior, ...] = Field(default=(), max_length=MAX_ITEMS)
    not_designed_for: tuple[str, ...] = Field(min_length=1, max_length=MAX_ITEMS)
