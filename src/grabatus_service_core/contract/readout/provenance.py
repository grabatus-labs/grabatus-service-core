"""Reproducibility: what would be needed to run this fit again."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from grabatus_service_core.contract.duplicates import duplicated
from grabatus_service_core.contract.readout.enums import ROLE_PATTERN

_FROZEN = ConfigDict(extra="forbid", frozen=True)

_SHA256_PATTERN = r"^[0-9a-f]{64}$"

# Bounds both collections on this model — input_digests and
# library_versions. Named for the model, not for the digests, because
# library versions are not digests and the old _MAX_DIGESTS said they
# were. Deliberately not enums.MAX_ITEMS (30): a future refactor must
# not silently swap one limit for the other.
_MAX_PROVENANCE_ITEMS = 20

# Library names are short identifiers (e.g. "mlxtend"); versions are short
# version strings (e.g. "0.23.1"). Neither is a place for raw data — an
# unbounded dict key or value here is exactly as good a side door as an
# unbounded string anywhere else in this package.
_MAX_LIBRARY_NAME_LENGTH = 120
_MAX_LIBRARY_VERSION_LENGTH = 64
_LibraryName = Annotated[str, StringConstraints(max_length=_MAX_LIBRARY_NAME_LENGTH)]
_LibraryVersion = Annotated[str, StringConstraints(max_length=_MAX_LIBRARY_VERSION_LENGTH)]


class InputDigest(BaseModel):
    """Hash of one input, so the same run can be identified later."""

    model_config = _FROZEN

    role: str = Field(min_length=1, max_length=32, pattern=ROLE_PATTERN)
    sha256: str = Field(pattern=_SHA256_PATTERN)


class Reproducibility(BaseModel):
    """Seed, timing, input hashes and library versions."""

    model_config = _FROZEN

    random_seed: int | None = None
    compute_duration_seconds: float = Field(ge=0.0)
    input_digests: tuple[InputDigest, ...] = Field(min_length=1, max_length=_MAX_PROVENANCE_ITEMS)
    library_versions: dict[_LibraryName, _LibraryVersion] = Field(
        min_length=1, max_length=_MAX_PROVENANCE_ITEMS
    )

    @field_validator("input_digests")
    @classmethod
    def _digest_roles_are_unique(
        cls,
        digests: tuple[InputDigest, ...],
    ) -> tuple[InputDigest, ...]:
        """Two hashes for one role make the run unreproducible, not better documented."""
        repeated = duplicated(digest.role for digest in digests)
        if repeated:
            raise ValueError(f"input_digest roles must be unique, got duplicates={repeated!r}")
        return digests
