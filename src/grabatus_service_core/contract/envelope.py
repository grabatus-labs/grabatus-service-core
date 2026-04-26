"""The Envelope: top-level metadata of every contract message."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict

Origin = Literal["web", "api", "mcp", "internal"]
ProtocolVersion = Literal["1.0"]


class Envelope(BaseModel):
    """Metadata that wraps every service request.

    Carries the protocol version (for forward/backward compatibility),
    a unique request_id (used as the idempotency key end-to-end), the
    creation timestamp, and the origin channel of the request.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_version: ProtocolVersion
    request_id: UUID
    created_at: AwareDatetime
    origin: Origin
