"""EchoComputeBackend: returns the input bytes verbatim under role 'echoed'."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel

from grabatus_service_core.ports.values import ComputeResult

if TYPE_CHECKING:
    from grabatus_service_core.ports.compute_context import ComputeContext
    from grabatus_service_core.ports.values import LoadedInputs


class EchoParameters(BaseModel):
    """Echo service has no parameters."""


class EchoComputeBackend:
    """Re-emits the 'payload' input under role 'echoed'."""

    REQUIRED_INPUT_ROLES: ClassVar[frozenset[str]] = frozenset({"payload"})
    OPTIONAL_INPUT_ROLES: ClassVar[frozenset[str]] = frozenset()
    OUTPUT_ROLES: ClassVar[frozenset[str]] = frozenset({"echoed"})

    def run(
        self,
        *,
        inputs: LoadedInputs,
        parameters: EchoParameters,
        context: ComputeContext,
    ) -> ComputeResult:
        # No readout yet: issue #11 — ModelFamily has no honest value for a
        # passthrough. The context this service would need is already here.
        del context
        return ComputeResult(
            by_role={"echoed": inputs.by_role["payload"]},
            metadata={"echo": True},
        )
