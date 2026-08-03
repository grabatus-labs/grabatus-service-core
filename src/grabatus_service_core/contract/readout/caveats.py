"""Caveat: a limitation paired with the conclusion it forbids."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from grabatus_service_core.contract.readout.enums import Severity

_FROZEN = ConfigDict(extra="forbid", frozen=True)


class Caveat(BaseModel):
    """A limitation stated together with what not to conclude from it.

    ``do_not_conclude`` is mandatory: a caveat without it is a disclaimer
    that changes nobody's reading.
    """

    model_config = _FROZEN

    severity: Severity
    statement: str = Field(min_length=1, max_length=500)
    do_not_conclude: str = Field(min_length=1, max_length=500)
