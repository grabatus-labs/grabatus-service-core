"""ServiceRunner: orchestrates the 8-step pipeline across runtime modes.

Three modes are supported:

- ``MONOLITH`` (default for local dev) — runs all 8 steps in-process.
- ``RECEIVER`` — runs steps 1-3 (decode, validate, authorize), then
  dispatches the validated contract bytes to a Cloud Run Job and
  returns immediately. The worker performs the heavy lifting.
- ``WORKER`` — runs all 8 steps; expected to be invoked from a
  ``CloudRunJobsDispatcher`` payload (raw JSON, no broker envelope).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Generic
from uuid import UUID

from grabatus_service_core.contract.base import ParamsT
from grabatus_service_core.contract.readout.enums import READOUT_OUTPUT_ROLE
from grabatus_service_core.contract.version import READOUT_PROTOCOL_VERSION
from grabatus_service_core.errors import (
    GrabatusServiceError,
    InvalidContractError,
)
from grabatus_service_core.runner.state import ExecutionResult
from grabatus_service_core.runner.steps import (
    authorize,
    decode,
    load_inputs,
    make_compute_context,
    notify_webhook,
    resolve_credentials,
    run_compute,
    save_outputs,
    validate,
    validate_readout,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from grabatus_service_core.contract.base import BaseServiceContract
    from grabatus_service_core.ports.authorization import UriAuthorizationPort
    from grabatus_service_core.ports.clock import ClockPort
    from grabatus_service_core.ports.compute import ComputeBackendPort
    from grabatus_service_core.ports.job_dispatcher import JobDispatcherPort
    from grabatus_service_core.ports.message import MessagePort
    from grabatus_service_core.ports.observability import ObservabilityPort
    from grabatus_service_core.ports.secrets import SecretsPort
    from grabatus_service_core.ports.storage import StoragePort
    from grabatus_service_core.ports.values import RawMessage, WriteReceipt
    from grabatus_service_core.ports.webhook import WebhookPort
    from grabatus_service_core.runner.state import WriteReceipts
    from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist


class RuntimeMode(StrEnum):
    """Selects which segment of the pipeline a runner instance executes."""

    RECEIVER = "receiver"
    WORKER = "worker"
    MONOLITH = "monolith"
    SHARED_RECEIVER = "shared-receiver"


@dataclass(frozen=True)
class ServiceRunner(Generic[ParamsT]):  # noqa: UP046 — TypeVar form needed for runtime use
    """Compose the 8 step functions into a single ``execute`` entry point.

    Constructed via :func:`build_runner`, which validates inter-field
    invariants (e.g., ``worker_job_name`` must be set in receiver mode).
    """

    contract_type: type[BaseServiceContract[ParamsT]]
    storage: StoragePort
    message: MessagePort
    webhook: WebhookPort
    compute: ComputeBackendPort
    secrets: SecretsPort
    authorizer: UriAuthorizationPort
    observability: ObservabilityPort
    clock: ClockPort
    job_dispatcher: JobDispatcherPort
    scheme_allowlist: SchemeAllowlist
    mode: RuntimeMode = RuntimeMode.MONOLITH
    worker_job_name: str | None = field(default=None)

    def execute(self, raw: RawMessage) -> ExecutionResult[ParamsT]:
        """Run the pipeline branch selected by ``self.mode``."""
        with self.observability.span("service_runner.execute", mode=self.mode.value):
            if self.mode is RuntimeMode.RECEIVER:
                return self._run_receiver(raw)
            return self._run_full_pipeline(raw)

    def _run_full_pipeline(self, raw: RawMessage) -> ExecutionResult[ParamsT]:
        request_id: UUID | None = None
        try:
            parsed = decode(raw=raw, message=self.message)
            validated = validate(parsed=parsed, contract_type=self.contract_type)
            request_id = validated.contract.envelope.request_id
            self._check_role_compatibility(validated.contract)
            authorized = authorize(
                validated=validated,
                authorizer=self.authorizer,
                scheme_allowlist=self.scheme_allowlist,
            )
            credentials = resolve_credentials(authorized=authorized, secrets=self.secrets)
            inputs = load_inputs(
                authorized=authorized,
                credentials=credentials,
                storage=self.storage,
            )
            context = make_compute_context(authorized=authorized, clock=self.clock)
            compute_result = run_compute(
                authorized=authorized,
                inputs=inputs,
                compute=self.compute,
                context=context,
            )
            validate_readout(result=compute_result, context=context)
            receipts = save_outputs(
                authorized=authorized,
                credentials=credentials,
                result=compute_result,
                storage=self.storage,
            )
            payload = self._build_success_payload(
                request_id=request_id,
                receipts=receipts,
                metadata=compute_result.metadata,
            )
            ack = notify_webhook(
                callback=authorized.contract.callback,
                payload=payload,
                webhook=self.webhook,
            )
            return ExecutionResult(
                request_id=request_id,
                status="ok",
                contract=authorized.contract,
                receipts=receipts,
                error=None,
                metadata=compute_result.metadata,
                webhook_ack=ack,
            )
        except GrabatusServiceError as exc:
            return self._make_error_result(request_id=request_id, error=exc)

    def _run_receiver(self, raw: RawMessage) -> ExecutionResult[ParamsT]:
        request_id: UUID | None = None
        try:
            parsed = decode(raw=raw, message=self.message)
            validated = validate(parsed=parsed, contract_type=self.contract_type)
            request_id = validated.contract.envelope.request_id
            self._check_role_compatibility(validated.contract)
            authorized = authorize(
                validated=validated,
                authorizer=self.authorizer,
                scheme_allowlist=self.scheme_allowlist,
            )
            worker_job_name = self.worker_job_name
            if worker_job_name is None:
                # Defense in depth: build_runner enforces this; direct
                # ServiceRunner(...) instantiation bypasses that check.
                raise ValueError(
                    "ServiceRunner in RECEIVER mode requires worker_job_name; "
                    "use build_runner() which enforces this invariant.",
                )
            contract_bytes = json.dumps(
                authorized.contract.model_dump(mode="json"),
            ).encode("utf-8")
            dispatched = self.job_dispatcher.dispatch(
                job_name=worker_job_name,
                payload=contract_bytes,
                request_id=request_id,
            )
            return ExecutionResult(
                request_id=request_id,
                status="ok",
                contract=authorized.contract,
                receipts=None,
                error=None,
                metadata={"dispatched_job_id": dispatched.job_id},
                webhook_ack=None,
            )
        except GrabatusServiceError as exc:
            return self._make_error_result(request_id=request_id, error=exc)

    def _check_role_compatibility(
        self,
        contract: BaseServiceContract[ParamsT],
    ) -> None:
        # Read role frozensets from the instance — works for both real
        # backends (where they're ClassVars on a per-call subclass made by
        # make_*_compute_backend) and MagicMock-style fakes that set them
        # as instance attributes.
        required = self.compute.REQUIRED_INPUT_ROLES
        optional = self.compute.OPTIONAL_INPUT_ROLES
        outputs_required = self._expected_output_roles(contract)
        declared_inputs = {item.role for item in contract.inputs}
        declared_outputs = {item.role for item in contract.outputs}
        accepted_inputs = required | optional
        missing = required - declared_inputs
        if missing:
            raise InvalidContractError(
                f"contract is missing required input roles {sorted(missing)!r}; "
                f"backend requires {sorted(required)!r}",
            )
        unknown = declared_inputs - accepted_inputs
        if unknown:
            raise InvalidContractError(
                f"contract declares unknown input roles {sorted(unknown)!r}; "
                f"backend accepts {sorted(accepted_inputs)!r}",
            )
        if declared_outputs != outputs_required:
            raise InvalidContractError(
                f"contract output roles {sorted(declared_outputs)!r} do not match "
                f"backend OUTPUT_ROLES {sorted(outputs_required)!r}",
            )

    def _expected_output_roles(
        self,
        contract: BaseServiceContract[ParamsT],
    ) -> frozenset[str]:
        """Add the readout role the SDK owns, so no service has to remember it.

        A service declares only the artifacts it computes. From protocol 1.1
        on, the readout is part of every contract whether the service thought
        about it or not.
        """
        if contract.envelope.protocol_version != READOUT_PROTOCOL_VERSION:
            return self.compute.OUTPUT_ROLES
        return self.compute.OUTPUT_ROLES | {READOUT_OUTPUT_ROLE}

    def _make_error_result(
        self,
        *,
        request_id: UUID | None,
        error: GrabatusServiceError,
    ) -> ExecutionResult[ParamsT]:
        self.observability.metric(
            "service_runner.errors",
            1.0,
            error_code=error.error_code,
            mode=self.mode.value,
        )
        return ExecutionResult(
            request_id=request_id or _PLACEHOLDER_REQUEST_ID,
            status="error",
            contract=None,
            receipts=None,
            error=error,
            metadata={"error_code": error.error_code, "error_message": str(error)},
            webhook_ack=None,
        )

    @staticmethod
    def _build_success_payload(
        *,
        request_id: UUID,
        receipts: WriteReceipts,
        metadata: Mapping[str, object],
    ) -> dict[str, Any]:
        return {
            "request_id": str(request_id),
            "status": "ok",
            "outputs": [_receipt_to_dict(role, r) for role, r in receipts.by_role.items()],
            "metadata": dict(metadata),
        }


_PLACEHOLDER_REQUEST_ID = UUID("00000000-0000-0000-0000-000000000000")


def _receipt_to_dict(role: str, receipt: WriteReceipt) -> dict[str, Any]:
    return {
        "role": role,
        "uri": receipt.uri,
        "bytes_written": receipt.bytes_written,
        "request_id_tag": receipt.request_id_tag,
    }


def build_runner(
    *,
    contract_type: type[BaseServiceContract[ParamsT]],
    storage: StoragePort,
    message: MessagePort,
    webhook: WebhookPort,
    compute: ComputeBackendPort,
    secrets: SecretsPort,
    authorizer: UriAuthorizationPort,
    observability: ObservabilityPort,
    clock: ClockPort,
    job_dispatcher: JobDispatcherPort,
    scheme_allowlist: SchemeAllowlist,
    mode: RuntimeMode = RuntimeMode.MONOLITH,
    worker_job_name: str | None = None,
) -> ServiceRunner[ParamsT]:
    """Construct a :class:`ServiceRunner` validating cross-field invariants."""
    if mode is RuntimeMode.RECEIVER and worker_job_name is None:
        raise ValueError(
            "build_runner: worker_job_name is required when mode=RuntimeMode.RECEIVER",
        )
    return ServiceRunner(
        contract_type=contract_type,
        storage=storage,
        message=message,
        webhook=webhook,
        compute=compute,
        secrets=secrets,
        authorizer=authorizer,
        observability=observability,
        clock=clock,
        job_dispatcher=job_dispatcher,
        scheme_allowlist=scheme_allowlist,
        mode=mode,
        worker_job_name=worker_job_name,
    )
