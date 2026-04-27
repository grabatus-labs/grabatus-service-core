"""OpaqueServiceContract: receiver-side contract that does not validate parameters.

The shared receiver does not know which service it is dispatching to until it
reads ``envelope.service.name``. So it must accept *any* parameters dict and
let the worker validate the parameters with its own typed schema.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from grabatus_service_core.contract.base import BaseServiceContract


class OpaqueParameters(BaseModel):
    """Parameters as a free-form mapping; only the worker validates the shape."""

    model_config = ConfigDict(extra="allow", frozen=True)


OpaqueServiceContract = BaseServiceContract[OpaqueParameters]
"""Type alias used by the shared receiver for envelope-only validation."""
