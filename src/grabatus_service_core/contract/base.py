"""BaseServiceContract: the generic top-level contract every service receives."""

from __future__ import annotations

from typing import Generic, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from grabatus_service_core.contract.callback import Callback
from grabatus_service_core.contract.duplicates import duplicated
from grabatus_service_core.contract.envelope import Envelope
from grabatus_service_core.contract.identity import Identity
from grabatus_service_core.contract.io_spec import (
    InputSpec,
    OutputSpec,
)
from grabatus_service_core.contract.references import References
from grabatus_service_core.contract.service_descriptor import (
    ServiceDescriptor,
)

_MAX_INPUTS = 10
# 10 service outputs plus the mandatory model_readout of protocol 1.1.
_MAX_OUTPUTS = 11

ParamsT = TypeVar("ParamsT", bound=BaseModel)


class BaseServiceContract(BaseModel, Generic[ParamsT]):  # noqa: UP046
    """Generic top-level contract that wraps every service request.

    A concrete service parameterizes this with its own ``Parameters``
    Pydantic model::

        class ForecastContract(BaseServiceContract[ForecastParameters]):
            pass

    The library validates every section here; service code only validates
    its own ``parameters`` payload.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    envelope: Envelope
    identity: Identity
    references: References
    service: ServiceDescriptor
    inputs: list[InputSpec] = Field(min_length=1, max_length=_MAX_INPUTS)
    outputs: list[OutputSpec] = Field(min_length=1, max_length=_MAX_OUTPUTS)
    callback: Callback
    parameters: ParamsT

    @model_validator(mode="after")
    def _input_roles_are_unique(self) -> Self:
        duplicates = duplicated(item.role for item in self.inputs)
        if duplicates:
            raise ValueError(
                f"input roles must be unique, got duplicates={duplicates!r}",
            )
        return self

    @model_validator(mode="after")
    def _output_roles_are_unique(self) -> Self:
        duplicates = duplicated(item.role for item in self.outputs)
        if duplicates:
            raise ValueError(
                f"output roles must be unique, got duplicates={duplicates!r}",
            )
        return self
