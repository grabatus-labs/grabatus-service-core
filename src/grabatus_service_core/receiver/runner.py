"""SharedReceiverRunner: validates envelope, dispatches to the right worker.

The ``execute`` method body is added in a follow-up task; this module
introduces the value objects and the runner skeleton.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from uuid import UUID

    from grabatus_service_core.errors import GrabatusServiceError
    from grabatus_service_core.ports.authorization import UriAuthorizationPort
    from grabatus_service_core.ports.clock import ClockPort
    from grabatus_service_core.ports.job_dispatcher import JobDispatcherPort
    from grabatus_service_core.ports.message import MessagePort
    from grabatus_service_core.ports.observability import ObservabilityPort
    from grabatus_service_core.ports.values import RawMessage
    from grabatus_service_core.receiver.registry import ServiceRegistry
    from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist


@dataclass(frozen=True, slots=True)
class ReceiverExecutionResult:
    """Outcome of dispatching one Pub/Sub envelope through the shared receiver."""

    request_id: UUID
    status: Literal["ok", "error"]
    dispatched_job_id: str | None
    error: GrabatusServiceError | None


@dataclass(frozen=True, slots=True)
class SharedReceiverAdapters:
    """Bundle of ports the shared receiver needs.

    Grouped into a dataclass so the factory signature stays clean.
    """

    message: MessagePort
    authorizer: UriAuthorizationPort
    job_dispatcher: JobDispatcherPort
    observability: ObservabilityPort
    clock: ClockPort


@dataclass(frozen=True, slots=True)
class SharedReceiverRunner:
    """Receiver pipeline: decode -> validate -> authorize -> dispatch.

    The ``execute`` method body is implemented in the next task.
    """

    adapters: SharedReceiverAdapters
    scheme_allowlist: SchemeAllowlist
    registry: ServiceRegistry

    def execute(
        self, raw: RawMessage
    ) -> ReceiverExecutionResult:  # pragma: no cover  # stub; body added in next task
        raise NotImplementedError(
            "SharedReceiverRunner.execute is implemented in a follow-up task",
        )
