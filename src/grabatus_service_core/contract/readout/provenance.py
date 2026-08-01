"""Reproducibility: what would be needed to run this fit again."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from grabatus_service_core.contract.readout.enums import ROLE_PATTERN

_FROZEN = ConfigDict(extra="forbid", frozen=True)

_SHA256_PATTERN = r"^[0-9a-f]{64}$"

# Not enums.MAX_ITEMS (30): this bounds input_digests and library_versions
# specifically, and the two happen to differ in value. Keeping a distinct
# name avoids a future refactor silently swapping one limit for the other.
_MAX_DIGESTS = 20


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
    input_digests: tuple[InputDigest, ...] = Field(min_length=1, max_length=_MAX_DIGESTS)
    library_versions: dict[str, str] = Field(min_length=1, max_length=_MAX_DIGESTS)
