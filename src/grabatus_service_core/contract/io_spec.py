"""InputSpec and OutputSpec: declarative I/O for service contracts."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import (
    AnyUrl,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from grabatus_service_core.contract.format_hints import (  # noqa: TCH001 — Pydantic v2 needs runtime access to FormatHints
    FormatHints,
)
from grabatus_service_core.contract.secret_ref import (  # noqa: TCH001 — Pydantic v2 needs runtime access to SecretRef
    SecretRef,
)

_ROLE_PATTERN = r"^[a-z][a-z0-9_]*$"

DataFormat = Literal["xlsx", "csv", "json", "parquet", "bigquery", "inline"]


class InputSpec(BaseModel):
    """Declarative description of an input to be loaded by the service.

    Each input carries a service-defined ``role`` (e.g. ``timeseries``,
    ``holidays``) which the service's ``ComputeBackendPort`` declares as
    required or optional. The library validates roles at contract time.

    The ``format_hints`` discriminator must match the ``format`` field; a
    mismatch is rejected by the validator at model creation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: str = Field(min_length=1, max_length=32, pattern=_ROLE_PATTERN)
    source_uri: AnyUrl
    format: DataFormat
    format_hints: FormatHints
    credential_ref: SecretRef | None = None

    @model_validator(mode="after")
    def _format_matches_hints(self) -> Self:
        if self.format_hints.format != self.format:
            raise ValueError(
                f"format_hints.format={self.format_hints.format!r} does not "
                f"match format={self.format!r}",
            )
        return self


Compression = Literal["none", "gzip", "zstd"]
WriteMode = Literal["overwrite", "append", "fail_if_exists"]


class OutputSpec(BaseModel):
    """Declarative description of an output the service must persist.

    Carries the destination URI, format, optional compression, and a
    write mode that adapters honor (overwrite/append/fail_if_exists).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: str = Field(min_length=1, max_length=32, pattern=_ROLE_PATTERN)
    destination_uri: AnyUrl
    format: DataFormat
    format_hints: FormatHints
    compression: Compression = "none"
    write_mode: WriteMode = "overwrite"
    credential_ref: SecretRef | None = None

    @model_validator(mode="after")
    def _format_matches_hints(self) -> Self:
        if self.format_hints.format != self.format:
            raise ValueError(
                f"format_hints.format={self.format_hints.format!r} does not "
                f"match format={self.format!r}",
            )
        return self
