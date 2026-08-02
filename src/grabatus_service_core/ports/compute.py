"""ComputeBackendPort: the only Port a service implements directly."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Protocol, runtime_checkable

if TYPE_CHECKING:
    from grabatus_service_core.ports.compute_context import ComputeContext
    from grabatus_service_core.ports.values import ComputeResult, LoadedInputs


@runtime_checkable
class ComputeBackendPort(Protocol):
    """Service-specific compute logic.

    The library validates at contract time that every required role is
    present in ``inputs`` and that no unknown role appears in ``outputs``.
    Implementers declare these sets as ``ClassVar`` so the runner can
    inspect them without instantiating.
    """

    REQUIRED_INPUT_ROLES: ClassVar[frozenset[str]]
    OPTIONAL_INPUT_ROLES: ClassVar[frozenset[str]]
    OUTPUT_ROLES: ClassVar[frozenset[str]]

    def run(
        self,
        *,
        inputs: LoadedInputs,
        parameters: Any,
        context: ComputeContext,
    ) -> ComputeResult:
        """Execute the computation and describe the run in a ``model_readout``.

        ``context`` carries the ids the readout demands; sourcing them
        anywhere else means inventing them.
        """
        ...
