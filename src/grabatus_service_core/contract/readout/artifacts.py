"""ArtifactDescription: a data dictionary for each numeric artefact.

The readout does not carry the numbers. It carries what each column of
each artefact means, so that reading the raw file does not require
guessing.
"""

from __future__ import annotations

from typing import Annotated, Final, Literal

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, UrlConstraints, field_validator

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

# settings._DEFAULT_ALLOWED_SCHEMES (the SDK's production default storage
# allowlist) plus `file`. `inline` is deliberately excluded even though
# InputSpec/OutputSpec permit it as a *format*: `inline://` embeds its
# payload directly in the URI — the same smuggling shape as `data:` — so
# an artifact, which only ever points at where a service already wrote a
# file, has no legitimate use for either scheme.
#
# `file` is a different case and belongs here: a bounded path with no
# embedded payload, and what every local run writes to
# (GBT_ALLOWED_SCHEMES="inline,file"). Leaving it out made the readout
# gate unsatisfiable in local mode for every service at once — see #18.
_ALLOWED_ARTIFACT_SCHEMES: Final[tuple[str, ...]] = ("gs", "bigquery", "secret", "file")

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

    @field_validator("uri", mode="before")
    @classmethod
    def _check_the_scheme_even_when_prebuilt(cls, uri: object) -> object:
        """Re-check an already-constructed ``AnyUrl`` against the allowlist.

        Pydantic applies ``UrlConstraints`` while *parsing* a URL; hand it a
        finished ``AnyUrl`` and the constraint is skipped entirely, so
        ``AnyUrl("data:...;base64,...")`` was accepted in Python and only
        rejected on the JSON round-trip the runner performs. A service unit
        test would pass and the same readout would fail in production.
        """
        return str(uri) if isinstance(uri, AnyUrl) else uri
