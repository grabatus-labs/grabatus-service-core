"""FakeComputeBackend: returns predefined output bytes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, cast

from grabatus_service_core.ports.values import ComputeResult

if TYPE_CHECKING:
    from collections.abc import Mapping

    from grabatus_service_core.ports.values import LoadedInputs


def make_fake_compute_backend(
    *,
    required_input_roles: frozenset[str],
    optional_input_roles: frozenset[str] = frozenset(),
    output_roles: frozenset[str],
    outputs: Mapping[str, bytes],
    metadata: Mapping[str, object] | None = None,
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
    return configured_cls(outputs=outputs, metadata=metadata)


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
    ) -> None:
        self._outputs = dict(outputs)
        self._metadata = dict(metadata or {})

    def run(self, *, inputs: LoadedInputs, parameters: Any) -> ComputeResult:  # noqa: ANN401
        del inputs, parameters
        return ComputeResult(by_role=self._outputs, metadata=self._metadata)
