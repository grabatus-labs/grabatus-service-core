"""ComputeContext: the run's identity, handed to the compute backend.

A backend produces numbers. The ``model_readout`` it must emit alongside
them also has to state *which run* produced them — ids that live in the
contract, which ``ComputeBackendPort.run`` never received. Without this
object the readout gate is unsatisfiable by any real service.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from grabatus_service_core.contract.readout.root import ReadoutRequest, ReadoutService
from grabatus_service_core.errors import UnknownOutputRoleError

if TYPE_CHECKING:
    from collections.abc import Mapping
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
    # Where each declared output is being written. The readout's
    # `artifacts[].uri` must name the real destination, and a backend that
    # cannot read it has no honest option left but to invent one.
    output_uris: Mapping[str, str]

    @classmethod
    def from_contract(
        cls,
        contract: BaseServiceContract[Any],
        *,
        generated_at: datetime,
    ) -> ComputeContext:
        """Project a validated contract into the subset a backend may see.

        The backend gets ids and its own output destinations, never the
        contract: callbacks, credentials and input URIs stay out.
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
            output_uris=MappingProxyType(
                {spec.role: str(spec.destination_uri) for spec in contract.outputs},
            ),
        )

    def artifact_uri(self, role: str) -> str:
        """Where ``role`` is being written, for the readout's ``artifacts[].uri``.

        Fails loudly on an unknown role: a silent fallback would put a
        plausible-looking wrong URI in the one document the client is told
        to trust.
        """
        try:
            return self.output_uris[role]
        except KeyError:
            raise UnknownOutputRoleError(
                f"contract declares no output role {role!r}; "
                f"declared roles are {sorted(self.output_uris)!r}",
            ) from None

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
