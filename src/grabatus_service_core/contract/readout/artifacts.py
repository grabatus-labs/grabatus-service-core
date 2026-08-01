"""ArtifactDescription: a data dictionary for each numeric artefact.

The readout does not carry the numbers. It carries what each column of
each artefact means, so that reading the raw file does not require
guessing.
"""

from __future__ import annotations

from typing import Literal

from pydantic import AnyUrl, BaseModel, ConfigDict, Field

from grabatus_service_core.contract.io_spec import DataFormat
from grabatus_service_core.contract.readout.enums import ROLE_PATTERN

_FROZEN = ConfigDict(extra="forbid", frozen=True)

_MAX_FIELDS = 100

FieldType = Literal["number", "integer", "string", "boolean", "date", "datetime"]


class FieldDescription(BaseModel):
    """One column of one artefact, in technical and plain terms."""

    model_config = _FROZEN

    name: str = Field(min_length=1, max_length=120)
    type: FieldType
    unit: str | None = Field(default=None, max_length=64)
    interval_level: float | None = Field(default=None, gt=0.0, lt=1.0)
    meaning: str = Field(min_length=1, max_length=500)
    read_as: str = Field(min_length=1, max_length=500)


class ArtifactDescription(BaseModel):
    """One numeric artefact the service wrote, and its field dictionary."""

    model_config = _FROZEN

    role: str = Field(min_length=1, max_length=32, pattern=ROLE_PATTERN)
    uri: AnyUrl
    format: DataFormat
    description: str = Field(min_length=1, max_length=500)
    fields: tuple[FieldDescription, ...] = Field(min_length=1, max_length=_MAX_FIELDS)
