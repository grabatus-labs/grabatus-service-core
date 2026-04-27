"""SharedReceiverRunner: value objects (execute body added in next task)."""

import json
from base64 import b64encode
from uuid import UUID, uuid4

import pytest

from grabatus_service_core.adapters.message_pubsub import PubSubMessagePort
from grabatus_service_core.contract.opaque import OpaqueParameters, OpaqueServiceContract
from grabatus_service_core.errors import (
    InvalidContractError,
    MalformedMessageError,
    UnauthorizedUriError,
    UnknownServiceError,
)
from grabatus_service_core.ports.values import RawMessage
from grabatus_service_core.receiver.registry import ServiceRegistry
from grabatus_service_core.receiver.runner import (
    ReceiverExecutionResult,
    SharedReceiverAdapters,
    SharedReceiverRunner,
)
from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist
from grabatus_service_core.testing import (
    AllowAllPolicy,
    FrozenClock,
    InMemoryJobDispatcher,
    NullObservability,
    RejectAllPolicy,
)
from grabatus_service_core.testing.factories import (
    make_contract,
    make_service_descriptor,
)


def test_receiver_execution_result_holds_status_and_request_id() -> None:
    rid = uuid4()
    result = ReceiverExecutionResult(
        request_id=rid,
        status="ok",
        dispatched_job_id="job-123",
        error=None,
    )
    assert result.request_id == rid
    assert result.status == "ok"
    assert result.dispatched_job_id == "job-123"
    assert result.error is None


def test_receiver_execution_result_is_frozen() -> None:
    result = ReceiverExecutionResult(
        request_id=uuid4(),
        status="ok",
        dispatched_job_id="j",
        error=None,
    )
    with pytest.raises((AttributeError, TypeError)):
        result.status = "error"  # type: ignore[misc]


def _build_opaque_contract(parameters: dict, service_name: str) -> OpaqueServiceContract:
    """Build an OpaqueServiceContract via the existing make_contract factory."""
    return make_contract(
        parameters=OpaqueParameters.model_validate(parameters),
        service=make_service_descriptor(name=service_name),
    )


def _build_pubsub_raw_message(contract: OpaqueServiceContract) -> RawMessage:
    """Wrap a contract in the {"message": {"data": <base64-JSON>}} envelope."""
    inner_json = json.dumps(contract.model_dump(mode="json")).encode("utf-8")
    wrapper = {"message": {"data": b64encode(inner_json).decode("ascii")}}
    return RawMessage(payload=json.dumps(wrapper).encode("utf-8"))


def _build_runner_with_registry(registry: ServiceRegistry) -> SharedReceiverRunner:
    return SharedReceiverRunner(
        adapters=SharedReceiverAdapters(
            message=PubSubMessagePort(),
            authorizer=AllowAllPolicy(),
            job_dispatcher=InMemoryJobDispatcher(),
            observability=NullObservability(),
            clock=FrozenClock("2026-04-27T12:00:00Z"),
        ),
        scheme_allowlist=SchemeAllowlist(allowed={"gs", "bigquery", "secret"}),
        registry=registry,
    )


def test_execute_happy_path_dispatches_to_correct_worker() -> None:
    contract = _build_opaque_contract({"any": "thing"}, service_name="forecast")
    raw = _build_pubsub_raw_message(contract)
    runner = _build_runner_with_registry(
        ServiceRegistry(by_name={"forecast": "grabatus-forecasting-worker"}),
    )

    result = runner.execute(raw)

    assert result.status == "ok"
    assert result.error is None
    assert result.request_id == contract.envelope.request_id
    dispatcher = runner.adapters.job_dispatcher
    assert isinstance(dispatcher, InMemoryJobDispatcher)
    assert len(dispatcher.dispatched) == 1
    assert dispatcher.dispatched[0].job_name == "grabatus-forecasting-worker"
    assert result.dispatched_job_id is not None


def test_execute_serializes_full_validated_contract_into_payload() -> None:
    contract = _build_opaque_contract({"x": 1}, service_name="forecast")
    raw = _build_pubsub_raw_message(contract)
    runner = _build_runner_with_registry(
        ServiceRegistry(by_name={"forecast": "grabatus-forecasting-worker"}),
    )

    runner.execute(raw)

    dispatcher = runner.adapters.job_dispatcher
    assert isinstance(dispatcher, InMemoryJobDispatcher)
    parsed = json.loads(dispatcher.dispatched[0].payload.decode("utf-8"))
    assert parsed["service"]["name"] == "forecast"
    assert parsed["parameters"] == {"x": 1}
    assert parsed["envelope"]["request_id"] == str(contract.envelope.request_id)


def test_execute_returns_malformed_message_error_with_placeholder_request_id() -> None:
    runner = _build_runner_with_registry(ServiceRegistry(by_name={"forecast": "fc"}))
    raw = RawMessage(payload=b"not-json")

    result = runner.execute(raw)

    assert result.status == "error"
    assert isinstance(result.error, MalformedMessageError)
    assert result.dispatched_job_id is None
    assert result.request_id == UUID("00000000-0000-0000-0000-000000000000")


def test_execute_returns_invalid_contract_error_when_envelope_missing() -> None:
    payload = json.dumps(
        {
            "message": {
                "data": b64encode(json.dumps({"missing": "envelope"}).encode()).decode(),
            },
        }
    )
    raw = RawMessage(payload=payload.encode("utf-8"))
    runner = _build_runner_with_registry(ServiceRegistry(by_name={"forecast": "fc"}))

    result = runner.execute(raw)

    assert result.status == "error"
    assert isinstance(result.error, InvalidContractError)
    assert result.dispatched_job_id is None


def test_execute_returns_unknown_service_error_when_name_not_in_registry() -> None:
    contract = _build_opaque_contract({"x": 1}, service_name="ghost-service")
    raw = _build_pubsub_raw_message(contract)
    runner = _build_runner_with_registry(ServiceRegistry(by_name={"forecast": "fc"}))

    result = runner.execute(raw)

    assert result.status == "error"
    assert isinstance(result.error, UnknownServiceError)
    assert "ghost-service" in str(result.error)
    assert result.dispatched_job_id is None
    assert result.request_id == contract.envelope.request_id


def test_execute_returns_unauthorized_uri_error_when_authorizer_rejects() -> None:
    contract = _build_opaque_contract({"x": 1}, service_name="forecast")
    raw = _build_pubsub_raw_message(contract)
    runner = SharedReceiverRunner(
        adapters=SharedReceiverAdapters(
            message=PubSubMessagePort(),
            authorizer=RejectAllPolicy(),
            job_dispatcher=InMemoryJobDispatcher(),
            observability=NullObservability(),
            clock=FrozenClock("2026-04-27T12:00:00Z"),
        ),
        scheme_allowlist=SchemeAllowlist(allowed={"gs", "bigquery", "secret"}),
        registry=ServiceRegistry(by_name={"forecast": "fc"}),
    )

    result = runner.execute(raw)

    assert result.status == "error"
    assert isinstance(result.error, UnauthorizedUriError)
    assert result.dispatched_job_id is None


def test_shared_receiver_runner_has_shared_receiver_mode() -> None:
    runner = _build_runner_with_registry(ServiceRegistry(by_name={"forecast": "fc"}))
    assert runner.mode.value == "shared-receiver"
