"""BaseServiceContract: the generic top-level contract every service receives."""

from __future__ import annotations

from typing import Generic, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from grabatus_service_core.contract.callback import Callback  # noqa: TCH001 — runtime
from grabatus_service_core.contract.envelope import Envelope  # noqa: TCH001 — runtime
from grabatus_service_core.contract.identity import Identity  # noqa: TCH001 — runtime
from grabatus_service_core.contract.io_spec import (  # noqa: TCH001 — runtime
    InputSpec,
    OutputSpec,
)
from grabatus_service_core.contract.references import References  # noqa: TCH001
from grabatus_service_core.contract.service_descriptor import (  # noqa: TCH001
    ServiceDescriptor,
)

_MAX_INPUTS = 10
_MAX_OUTPUTS = 10

ParamsT = TypeVar("ParamsT", bound=BaseModel)


class BaseServiceContract(BaseModel, Generic[ParamsT]):
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
        roles = [item.role for item in self.inputs]
        if len(roles) != len(set(roles)):
            duplicates = sorted({r for r in roles if roles.count(r) > 1})
            raise ValueError(
                f"input roles must be unique, got duplicates={duplicates!r}",
            )
        return self

    @model_validator(mode="after")
    def _output_roles_are_unique(self) -> Self:
        roles = [item.role for item in self.outputs]
        if len(roles) != len(set(roles)):
            duplicates = sorted({r for r in roles if roles.count(r) > 1})
            raise ValueError(
                f"output roles must be unique, got duplicates={duplicates!r}",
            )
        return self
