"""End-to-end pipeline tests with all-fake adapters.

Exercises the same wire format a production deployment receives — a
Pub/Sub push envelope (base64 + JSON) — through every step of the
runner, asserting on the side effects each step is supposed to leave
behind. The compute backend is the FakeComputeBackend; everything else
is a real adapter where possible (PubSubMessagePort, SchemeAllowlist,
TenantPrefixPolicy) and an in-memory fake otherwise.
"""

from __future__ import annotations

import base64
import gzip
import json
from typing import Any

import pytest
from pydantic import BaseModel

from grabatus_service_core.adapters.message_pubsub import PubSubMessagePort
from grabatus_service_core.contract.base import BaseServiceContract
from grabatus_service_core.errors import (
    InvalidContractError,
    UnauthorizedUriError,
    UnsupportedSchemeError,
)
from grabatus_service_core.ports.values import RawMessage
from grabatus_service_core.runner import RuntimeMode, build_runner
from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist
from grabatus_service_core.security.tenant_prefix_policy import TenantPrefixPolicy
from grabatus_service_core.testing import (
    FrozenClock,
    InMemoryJobDispatcher,
    InMemorySecretsAdapter,
    InMemoryStorage,
    NullObservability,
    RecordingWebhookNotifier,
    make_callback,
    make_contract,
    make_envelope,
    make_fake_compute_backend,
    make_identity,
    make_input_spec,
    make_output_spec,
    make_references,
    make_service_descriptor,
)


class _ForecastParams(BaseModel):
    horizon: int = 30
    freq: str = "D"


_TENANT = "grabatus"
_USER = "999"
_BUCKET = f"gbt-storage-{_TENANT}"
_INPUT_URI = f"gs://{_BUCKET}/user_{_USER}/in.xlsx"
_OUTPUT_URI = f"gs://{_BUCKET}/user_{_USER}/out.json"
_INPUT_BYTES = b"timeseries-rows"
_FORECAST_BYTES = json.dumps({"forecast": [1, 2, 3]}).encode("utf-8")


def _contract_dict(
    *,
    inputs: list[Any] | None = None,
    outputs: list[Any] | None = None,
) -> dict[str, Any]:
    contract = make_contract(
        parameters=_ForecastParams(horizon=30, freq="D"),
        envelope=make_envelope(),
        identity=make_identity(user_id=_USER, tenant_id=_TENANT),
        references=make_references(),
        service=make_service_descriptor(name="forecasting", version="1.0.0"),
        inputs=inputs or [make_input_spec(role="timeseries", source_uri=_INPUT_URI, fmt="xlsx")],
        outputs=outputs
        or [
            make_output_spec(role="result_json", destination_uri=_OUTPUT_URI, fmt="json"),
        ],
        callback=make_callback(),
    )
    return contract.model_dump(mode="json")


def _pubsub_envelope_for(payload: dict[str, Any]) -> bytes:
    inner = json.dumps(payload).encode("utf-8")
    wrapper = {"message": {"data": base64.b64encode(inner).decode("ascii")}}
    return json.dumps(wrapper).encode("utf-8")


def _runner(
    *,
    mode: RuntimeMode = RuntimeMode.MONOLITH,
    storage: InMemoryStorage | None = None,
    webhook: RecordingWebhookNotifier | None = None,
    job_dispatcher: InMemoryJobDispatcher | None = None,
    output: bytes = _FORECAST_BYTES,
    worker_job_name: str | None = None,
) -> Any:
    return build_runner(
        contract_type=BaseServiceContract[_ForecastParams],
        storage=storage or InMemoryStorage(seed={_INPUT_URI: _INPUT_BYTES}),
        message=PubSubMessagePort(),
        webhook=webhook or RecordingWebhookNotifier(),
        compute=make_fake_compute_backend(
            required_input_roles=frozenset({"timeseries"}),
            output_roles=frozenset({"result_json"}),
            outputs={"result_json": output},
            metadata={"model": "prophet", "version": "1.0"},
        ),
        secrets=InMemorySecretsAdapter(seed={}),
        authorizer=TenantPrefixPolicy(bucket_prefix="gbt-storage"),
        observability=NullObservability(),
        clock=FrozenClock(iso_string="2026-04-26T00:00:00Z"),
        job_dispatcher=job_dispatcher or InMemoryJobDispatcher(),
        scheme_allowlist=SchemeAllowlist(allowed={"gs", "https", "secret"}),
        mode=mode,
        worker_job_name=worker_job_name,
    )


# ---------- happy path through the full pipeline ----------


def test_pubsub_push_to_webhook_round_trip() -> None:
    storage = InMemoryStorage(seed={_INPUT_URI: _INPUT_BYTES})
    webhook = RecordingWebhookNotifier()
    runner = _runner(storage=storage, webhook=webhook)

    raw = RawMessage(payload=_pubsub_envelope_for(_contract_dict()))
    result = runner.execute(raw)

    assert result.status == "ok"
    assert result.error is None
    assert result.receipts is not None
    written = storage._objects[_OUTPUT_URI]
    assert written == _FORECAST_BYTES
    assert len(webhook.calls) == 1
    payload = webhook.calls[0].payload
    assert payload["status"] == "ok"
    assert payload["outputs"][0]["uri"] == _OUTPUT_URI
    assert payload["outputs"][0]["bytes_written"] == len(_FORECAST_BYTES)


def test_request_id_propagates_from_envelope_to_webhook_payload() -> None:
    webhook = RecordingWebhookNotifier()
    runner = _runner(webhook=webhook)
    contract_dict = _contract_dict()
    rid = contract_dict["envelope"]["request_id"]

    runner.execute(RawMessage(payload=_pubsub_envelope_for(contract_dict)))

    assert webhook.calls[0].payload["request_id"] == rid


def test_compute_metadata_propagates_to_webhook_payload() -> None:
    webhook = RecordingWebhookNotifier()
    runner = _runner(webhook=webhook)

    runner.execute(RawMessage(payload=_pubsub_envelope_for(_contract_dict())))

    metadata = webhook.calls[0].payload["metadata"]
    assert metadata == {"model": "prophet", "version": "1.0"}


def test_pipeline_can_carry_gzip_encoded_output_bytes() -> None:
    # Mirrors the legacy forecasting pattern: compute returns gzip bytes,
    # storage round-trips them verbatim, webhook reports bytes_written
    # against the compressed size.
    compressed = gzip.compress(_FORECAST_BYTES)
    storage = InMemoryStorage(seed={_INPUT_URI: _INPUT_BYTES})
    runner = _runner(storage=storage, output=compressed)

    runner.execute(RawMessage(payload=_pubsub_envelope_for(_contract_dict())))

    assert storage._objects[_OUTPUT_URI] == compressed
    assert gzip.decompress(storage._objects[_OUTPUT_URI]) == _FORECAST_BYTES


# ---------- security failures surface as ExecutionResult.status="error" ----------


def test_unauthorized_uri_yields_error_result_and_no_webhook_call() -> None:
    cross_tenant_uri = "gs://gbt-storage-other-tenant/user_999/in.xlsx"
    contract = _contract_dict(
        inputs=[
            make_input_spec(role="timeseries", source_uri=cross_tenant_uri, fmt="xlsx"),
        ],
    )
    webhook = RecordingWebhookNotifier()
    runner = _runner(webhook=webhook)

    result = runner.execute(RawMessage(payload=_pubsub_envelope_for(contract)))

    assert result.status == "error"
    assert isinstance(result.error, UnauthorizedUriError)
    assert webhook.calls == []


def test_disallowed_scheme_yields_unsupported_scheme_error_result() -> None:
    contract = _contract_dict(
        inputs=[
            make_input_spec(
                role="timeseries",
                source_uri="ftp://no/in.csv",
                fmt="csv",
                hints={"format": "csv", "delimiter": ","},
            ),
        ],
    )
    runner = _runner()

    result = runner.execute(RawMessage(payload=_pubsub_envelope_for(contract)))

    assert result.status == "error"
    assert isinstance(result.error, UnsupportedSchemeError)


def test_user_path_segment_must_match_identity_user_id() -> None:
    other_user_uri = f"gs://{_BUCKET}/user_other/in.xlsx"
    contract = _contract_dict(
        inputs=[make_input_spec(role="timeseries", source_uri=other_user_uri)],
    )
    runner = _runner()

    result = runner.execute(RawMessage(payload=_pubsub_envelope_for(contract)))

    assert result.status == "error"
    assert isinstance(result.error, UnauthorizedUriError)


# ---------- validation failures ----------


def test_missing_envelope_yields_invalid_contract_error_result() -> None:
    bad = _contract_dict()
    del bad["envelope"]
    runner = _runner()

    result = runner.execute(RawMessage(payload=_pubsub_envelope_for(bad)))

    assert result.status == "error"
    assert isinstance(result.error, InvalidContractError)


def test_envelope_with_unsupported_protocol_version_is_rejected() -> None:
    bad = _contract_dict()
    bad["envelope"]["protocol_version"] = "9.9"
    runner = _runner()

    result = runner.execute(RawMessage(payload=_pubsub_envelope_for(bad)))

    assert result.status == "error"
    # The literal Pydantic check fires first ("9.9" not in Literal[...]),
    # so it surfaces as InvalidContractError rather than
    # UnsupportedProtocolVersionError. Both are acceptable.
    assert result.error is not None


# ---------- receiver mode end-to-end ----------


def test_receiver_mode_dispatches_to_worker_with_validated_contract() -> None:
    dispatcher = InMemoryJobDispatcher()
    runner = _runner(
        mode=RuntimeMode.RECEIVER,
        worker_job_name="forecasting-worker",
        job_dispatcher=dispatcher,
    )

    result = runner.execute(RawMessage(payload=_pubsub_envelope_for(_contract_dict())))

    assert result.status == "ok"
    assert result.receipts is None
    assert len(dispatcher.dispatched) == 1
    record = dispatcher.dispatched[0]
    assert record.job_name == "forecasting-worker"
    dispatched_contract = json.loads(record.payload)
    assert dispatched_contract["service"]["name"] == "forecasting"
    assert dispatched_contract["parameters"]["horizon"] == 30


def test_receiver_then_worker_round_trip_persists_outputs_and_notifies() -> None:
    # Step 1: receiver receives Pub/Sub push, dispatches to worker
    dispatcher = InMemoryJobDispatcher()
    storage = InMemoryStorage(seed={_INPUT_URI: _INPUT_BYTES})
    receiver = _runner(
        mode=RuntimeMode.RECEIVER,
        worker_job_name="forecasting-worker",
        storage=storage,
        job_dispatcher=dispatcher,
    )
    receiver.execute(RawMessage(payload=_pubsub_envelope_for(_contract_dict())))
    assert len(dispatcher.dispatched) == 1
    worker_payload = dispatcher.dispatched[0].payload

    # Step 2: worker invoked with the validated contract bytes (no Pub/Sub envelope)
    webhook = RecordingWebhookNotifier()
    worker = build_runner(
        contract_type=BaseServiceContract[_ForecastParams],
        storage=storage,
        message=_RawJsonMessagePort(),  # no Pub/Sub wrapper on the worker side
        webhook=webhook,
        compute=make_fake_compute_backend(
            required_input_roles=frozenset({"timeseries"}),
            output_roles=frozenset({"result_json"}),
            outputs={"result_json": _FORECAST_BYTES},
            metadata={},
        ),
        secrets=InMemorySecretsAdapter(seed={}),
        authorizer=TenantPrefixPolicy(bucket_prefix="gbt-storage"),
        observability=NullObservability(),
        clock=FrozenClock(iso_string="2026-04-26T00:00:00Z"),
        job_dispatcher=InMemoryJobDispatcher(),
        scheme_allowlist=SchemeAllowlist(allowed={"gs", "https", "secret"}),
        mode=RuntimeMode.WORKER,
    )
    worker_result = worker.execute(RawMessage(payload=worker_payload))

    assert worker_result.status == "ok"
    assert worker_result.receipts is not None
    assert storage._objects[_OUTPUT_URI] == _FORECAST_BYTES
    assert len(webhook.calls) == 1


# Local helper: a MessagePort that round-trips raw JSON without Pub/Sub framing.
# Worker mode receives the validated contract bytes directly from the Cloud Run
# Job payload, so it does not see a {"message": {"data": "..."}} envelope.


class _RawJsonMessagePort:
    def decode(self, raw: RawMessage) -> dict[str, Any]:
        decoded = json.loads(raw.payload.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError(f"expected dict, got {type(decoded).__name__}")
        return decoded

    def encode(self, envelope: dict[str, Any]) -> bytes:
        return json.dumps(envelope).encode("utf-8")


@pytest.mark.parametrize(
    "horizon",
    [1, 7, 30, 90, 365],
)
def test_horizon_parameter_round_trips_through_pipeline(horizon: int) -> None:
    contract = _contract_dict()
    contract["parameters"]["horizon"] = horizon
    runner = _runner()

    result = runner.execute(RawMessage(payload=_pubsub_envelope_for(contract)))

    assert result.status == "ok"
    assert result.contract is not None
    assert result.contract.parameters.horizon == horizon
