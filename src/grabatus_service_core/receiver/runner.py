"""SharedReceiverRunner: validates envelope, dispatches to the right worker.

The receiver does not know which service it is dispatching to until it
reads ``envelope.service.name``. So it validates the contract against
``OpaqueServiceContract`` (parameters left opaque) and resolves the
target Cloud Run Job via a ``ServiceRegistry``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from grabatus_service_core.contract.opaque import OpaqueServiceContract
from grabatus_service_core.errors import GrabatusServiceError
from grabatus_service_core.runner.steps import authorize, decode, validate

if TYPE_CHECKING:
    from grabatus_service_core.ports.authorization import UriAuthorizationPort
    from grabatus_service_core.ports.clock import ClockPort
    from grabatus_service_core.ports.job_dispatcher import JobDispatcherPort
    from grabatus_service_core.ports.message import MessagePort
    from grabatus_service_core.ports.observability import ObservabilityPort
    from grabatus_service_core.ports.values import RawMessage
    from grabatus_service_core.receiver.registry import ServiceRegistry
    from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist


_PLACEHOLDER_REQUEST_ID = UUID("00000000-0000-0000-0000-000000000000")


@dataclass(frozen=True, slots=True)
class ReceiverExecutionResult:
    """Outcome of dispatching one Pub/Sub envelope through the shared receiver."""

    request_id: UUID
    status: Literal["ok", "error"]
    dispatched_job_id: str | None
    error: GrabatusServiceError | None


@dataclass(frozen=True, slots=True)
class SharedReceiverAdapters:
    """Bundle of ports the shared receiver needs."""

    message: MessagePort
    authorizer: UriAuthorizationPort
    job_dispatcher: JobDispatcherPort
    observability: ObservabilityPort
    clock: ClockPort


@dataclass(frozen=True, slots=True)
class SharedReceiverRunner:
    """Receiver pipeline: decode -> validate -> authorize -> dispatch."""

    adapters: SharedReceiverAdapters
    scheme_allowlist: SchemeAllowlist
    registry: ServiceRegistry

    def execute(self, raw: RawMessage) -> ReceiverExecutionResult:
        """Decode, validate, authorize, resolve target worker, dispatch."""
        request_id: UUID | None = None
        with self.adapters.observability.span("shared_receiver.execute"):
            try:
                parsed = decode(raw=raw, message=self.adapters.message)
                validated = validate(
                    parsed=parsed,
                    contract_type=OpaqueServiceContract,
                )
                request_id = validated.contract.envelope.request_id
                authorized = authorize(
                    validated=validated,
                    authorizer=self.adapters.authorizer,
                    scheme_allowlist=self.scheme_allowlist,
                )
                worker_job = self.registry.resolve(authorized.contract.service.name)
                contract_bytes = json.dumps(
                    authorized.contract.model_dump(mode="json"),
                ).encode("utf-8")
                dispatched = self.adapters.job_dispatcher.dispatch(
                    job_name=worker_job,
                    payload=contract_bytes,
                    request_id=request_id,
                )
                return ReceiverExecutionResult(
                    request_id=request_id,
                    status="ok",
                    dispatched_job_id=dispatched.job_id,
                    error=None,
                )
            except GrabatusServiceError as exc:
                self.adapters.observability.metric(
                    "shared_receiver.errors",
                    1.0,
                    error_code=exc.error_code,
                )
                return ReceiverExecutionResult(
                    request_id=request_id or _PLACEHOLDER_REQUEST_ID,
                    status="error",
                    dispatched_job_id=None,
                    error=exc,
                )
