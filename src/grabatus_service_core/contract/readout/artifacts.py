"""ArtifactDescription: a data dictionary for each numeric artefact.

The readout does not carry the numbers. It carries what each column of
each artefact means, so that reading the raw file does not require
guessing.
"""

from __future__ import annotations

from typing import Annotated, Final, Literal

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, UrlConstraints

from grabatus_service_core.contract.io_spec import DataFormat
from grabatus_service_core.contract.readout.enums import ROLE_PATTERN

_FROZEN = ConfigDict(extra="forbid", frozen=True)

_MAX_FIELDS = 100

# A generous bound for a storage URI (bucket + path), and nowhere near
# enough room to smuggle a payload the way a `data:` URI would
# (`data:application/json;base64,<400 KB>` validated as a plain AnyUrl —
# spec §4.3's raw-data-in prohibition applies to a URI just as much as to
# a string field).
_MAX_URI_LENGTH: Final[int] = 2048

# Mirrors settings._DEFAULT_ALLOWED_SCHEMES (the SDK's own production
# default storage scheme allowlist) rather than inventing a parallel list.
# `inline` is deliberately excluded even though InputSpec/OutputSpec permit
# it as a *format*: `inline://` embeds its payload directly in the URI —
# the same smuggling shape as `data:` — so an artifact, which only ever
# points at where a service already wrote a file, has no legitimate use
# for either scheme.
_ALLOWED_ARTIFACT_SCHEMES: Final[tuple[str, ...]] = ("gs", "bigquery", "secret")

ArtifactUri = Annotated[
    AnyUrl,
    UrlConstraints(max_length=_MAX_URI_LENGTH, allowed_schemes=list(_ALLOWED_ARTIFACT_SCHEMES)),
]

# Pydantic does not project `allowed_schemes` into the JSON Schema, so a
# consumer validating against the published snapshot — which is exactly
# what the Django platform does — would accept `data:` while the model
# rejects it. Derived from the tuple above so the two cannot drift.
ARTIFACT_URI_PATTERN: Final[str] = f"^({'|'.join(_ALLOWED_ARTIFACT_SCHEMES)})://"

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
    uri: ArtifactUri = Field(json_schema_extra={"pattern": ARTIFACT_URI_PATTERN})
    format: DataFormat
    description: str = Field(min_length=1, max_length=500)
    fields: tuple[FieldDescription, ...] = Field(min_length=1, max_length=_MAX_FIELDS)
