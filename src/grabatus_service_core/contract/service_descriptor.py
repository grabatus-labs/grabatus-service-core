"""ServiceDescriptor: identifies the target service and its version."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

_SERVICE_SLUG_PATTERN = r"^[a-z][a-z0-9_-]*$"
_SEMVER_PATTERN = r"^\d+\.\d+\.\d+$"


class ServiceDescriptor(BaseModel):
    """Identifies which service handles the request and at what version.

    Service ``name`` is a lowercase slug; ``version`` is strict
    ``MAJOR.MINOR.PATCH`` semver — pre-release and build metadata are not
    accepted in the contract (services release stable versions only).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=64, pattern=_SERVICE_SLUG_PATTERN)
    version: str = Field(min_length=5, max_length=32, pattern=_SEMVER_PATTERN)
