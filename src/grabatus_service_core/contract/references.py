"""References: platform-side IDs that round-trip in the webhook response."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class References(BaseModel):
    """Opaque IDs from the Grabatus platform.

    The service does not interpret these — they are echoed back in the
    webhook callback so the platform can correlate the response with its
    own database records.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    parameter_id: str = Field(min_length=1, max_length=128)
    result_id: str = Field(min_length=1, max_length=128)
