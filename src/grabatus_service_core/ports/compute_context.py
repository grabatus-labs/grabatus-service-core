"""ComputeContext: the run's identity, handed to the compute backend.

A backend produces numbers. The ``model_readout`` it must emit alongside
them also has to state *which run* produced them — ids that live in the
contract, which ``ComputeBackendPort.run`` never received. Without this
object the readout gate is unsatisfiable by any real service.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from grabatus_service_core.contract.readout.root import ReadoutRequest, ReadoutService

if TYPE_CHECKING:
    from datetime import datetime

    from grabatus_service_core.contract.base import BaseServiceContract
    from grabatus_service_core.contract.envelope import Origin


@dataclass(frozen=True, slots=True)
class ComputeContext:
    """Contract-derived facts a backend cannot know on its own.

    Built by the runner from the validated contract, so a backend never
    parses the contract itself and never invents an id.
    """

    request_id: str
    result_id: str
    parameter_id: str
    tenant_id: str
    origin: Origin
    service_name: str
    service_version: str
    # From the runner's ClockPort, not wall clock: a backend calling
    # datetime.now() itself would make its own readout untestable.
    generated_at: datetime

    @classmethod
    def from_contract(
        cls,
        contract: BaseServiceContract[Any],
        *,
        generated_at: datetime,
    ) -> ComputeContext:
        """Project a validated contract into the subset a backend may see.

        The backend gets ids, never the contract: callbacks, credentials
        and URIs are none of its business.
        """
        return cls(
            request_id=str(contract.envelope.request_id),
            result_id=contract.references.result_id,
            parameter_id=contract.references.parameter_id,
            tenant_id=contract.identity.tenant_id,
            origin=contract.envelope.origin,
            service_name=contract.service.name,
            service_version=contract.service.version,
            generated_at=generated_at,
        )

    def readout_request(self) -> ReadoutRequest:
        """Build the readout's ``request`` block, so no service maps it by hand.

        Cannot raise: every constraint on :class:`ReadoutRequest` was copied
        from the contract models these values come from.
        """
        return ReadoutRequest(
            request_id=self.request_id,
            result_id=self.result_id,
            parameter_id=self.parameter_id,
            tenant_id=self.tenant_id,
            origin=self.origin,
        )

    def readout_service(self) -> ReadoutService:
        """Build the readout's ``service`` block from the contract's descriptor."""
        return ReadoutService(name=self.service_name, version=self.service_version)
