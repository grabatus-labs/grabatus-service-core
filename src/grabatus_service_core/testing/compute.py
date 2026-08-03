"""FakeComputeBackend: returns predefined output bytes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, cast

from grabatus_service_core.contract.readout.enums import READOUT_OUTPUT_ROLE
from grabatus_service_core.ports.values import ComputeResult
from grabatus_service_core.testing.readout import make_model_readout

if TYPE_CHECKING:
    from collections.abc import Mapping

    from grabatus_service_core.ports.compute_context import ComputeContext
    from grabatus_service_core.ports.values import LoadedInputs


def make_fake_compute_backend(
    *,
    required_input_roles: frozenset[str],
    optional_input_roles: frozenset[str] = frozenset(),
    output_roles: frozenset[str],
    outputs: Mapping[str, bytes],
    metadata: Mapping[str, object] | None = None,
    emit_readout: bool = True,
) -> FakeComputeBackend:
    """Build a FakeComputeBackend whose role frozensets are configured per-call.

    The role declarations live on a freshly created subclass so two
    distinct fakes can declare different role sets in the same test file
    without leaking state to each other.
    """
    cls_name = "FakeComputeBackend_Configured"
    cls_namespace: dict[str, Any] = {
        "REQUIRED_INPUT_ROLES": required_input_roles,
        "OPTIONAL_INPUT_ROLES": optional_input_roles,
        "OUTPUT_ROLES": output_roles,
    }
    configured_cls = cast(
        "type[FakeComputeBackend]",
        type(cls_name, (FakeComputeBackend,), cls_namespace),
    )
    return configured_cls(outputs=outputs, metadata=metadata, emit_readout=emit_readout)


class FakeComputeBackend:
    """Test double for ComputeBackendPort with declarative outputs.

    Direct instantiation declares no roles (empty frozensets). Tests that
    need a backend with specific role declarations should call
    :func:`make_fake_compute_backend` instead, which builds a configured
    subclass whose ClassVars are isolated from other test instances.
    """

    REQUIRED_INPUT_ROLES: ClassVar[frozenset[str]] = frozenset()
    OPTIONAL_INPUT_ROLES: ClassVar[frozenset[str]] = frozenset()
    OUTPUT_ROLES: ClassVar[frozenset[str]] = frozenset()

    def __init__(
        self,
        *,
        outputs: Mapping[str, bytes],
        metadata: Mapping[str, object] | None = None,
        emit_readout: bool = True,
    ) -> None:
        self._outputs = dict(outputs)
        self._metadata = dict(metadata or {})
        self._emit_readout = emit_readout

    def run(
        self,
        *,
        inputs: LoadedInputs,
        parameters: Any,  # noqa: ANN401
        context: ComputeContext,
    ) -> ComputeResult:
        del inputs, parameters
        return ComputeResult(by_role=self._resolved_outputs(context), metadata=self._metadata)

    def _resolved_outputs(self, context: ComputeContext) -> dict[str, bytes]:
        """Supply the readout the runner now demands, unless the test opted out.

        The identity blocks come from ``context``, never from the canned
        defaults: a fake that stamped its own ids would fail the runner's
        mismatch check on every real contract.

        Tests that pass their own ``model_readout`` keep it — that is how an
        invalid readout gets through to the runtime gate.
        """
        if not self._emit_readout or READOUT_OUTPUT_ROLE in self._outputs:
            return self._outputs
        readout = make_model_readout(
            generated_at=context.generated_at,
            request=context.readout_request(),
            service=context.readout_service(),
        )
        return self._outputs | {READOUT_OUTPUT_ROLE: readout.model_dump_json().encode("utf-8")}
