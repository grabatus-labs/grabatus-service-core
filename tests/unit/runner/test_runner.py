"""Tests for ServiceRunner orchestrator and build_runner factory."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from grabatus_service_core.contract.base import BaseServiceContract
from grabatus_service_core.errors import (
    ComputeError,
    InputNotFoundError,
    InvalidContractError,
    MissingReadoutError,
    OutputWriteError,
)
from grabatus_service_core.ports.values import Credentials, RawMessage
from grabatus_service_core.runner import (
    RuntimeMode,
    ServiceRunner,
    build_runner,
)
from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist
from grabatus_service_core.testing import (
    AllowAllPolicy,
    FrozenClock,
    InMemoryJobDispatcher,
    InMemoryMessagePort,
    InMemorySecretsAdapter,
    InMemoryStorage,
    NullObservability,
    RecordingWebhookNotifier,
    make_contract,
    make_fake_compute_backend,
    make_input_spec,
    make_output_spec,
)


class _Params(BaseModel):
    horizon: int = 30


def _scheme_allowlist() -> SchemeAllowlist:
    return SchemeAllowlist(allowed={"gs", "https"})


def _ok_storage() -> InMemoryStorage:
    return InMemoryStorage(
        seed={"gs://gbt-storage-grabatus/user_999/in.xlsx": b"raw-bytes"},
    )


def _backend(*, output: bytes = b"forecast-bytes") -> object:
    return make_fake_compute_backend(
        required_input_roles=frozenset({"timeseries"}),
        output_roles=frozenset({"result_json"}),
        outputs={"result_json": output},
        metadata={"model": "prophet"},
    )


def _runner(
    **overrides: Any,
) -> ServiceRunner[_Params]:
    defaults: dict[str, Any] = {
        "contract_type": BaseServiceContract[_Params],
        "storage": _ok_storage(),
        "message": InMemoryMessagePort(),
        "webhook": RecordingWebhookNotifier(),
        "compute": _backend(),
        "secrets": InMemorySecretsAdapter(seed={}),
        "authorizer": AllowAllPolicy(),
        "observability": NullObservability(),
        "clock": FrozenClock(iso_string="2026-04-26T00:00:00Z"),
        "job_dispatcher": InMemoryJobDispatcher(),
        "scheme_allowlist": _scheme_allowlist(),
        "mode": RuntimeMode.MONOLITH,
    }
    defaults.update(overrides)
    return build_runner(**defaults)


def _raw_for(contract_dict: dict[str, Any]) -> RawMessage:
    return RawMessage(payload=json.dumps(contract_dict).encode("utf-8"))


def _valid_contract_dict() -> dict[str, Any]:
    return make_contract(parameters=_Params(horizon=30)).model_dump(mode="json")


# ---------- RuntimeMode ----------


def test_runtime_mode_has_three_values() -> None:
    assert RuntimeMode.RECEIVER.value == "receiver"
    assert RuntimeMode.WORKER.value == "worker"
    assert RuntimeMode.MONOLITH.value == "monolith"


# ---------- build_runner ----------


def test_build_runner_returns_service_runner_instance() -> None:
    runner = _runner()

    assert isinstance(runner, ServiceRunner)
    assert runner.mode is RuntimeMode.MONOLITH


def test_build_runner_rejects_receiver_mode_without_worker_job_name() -> None:
    with pytest.raises(ValueError, match="worker_job_name"):
        _runner(mode=RuntimeMode.RECEIVER)


def test_build_runner_accepts_receiver_mode_with_worker_job_name() -> None:
    runner = _runner(mode=RuntimeMode.RECEIVER, worker_job_name="forecast-worker")

    assert runner.mode is RuntimeMode.RECEIVER
    assert runner.worker_job_name == "forecast-worker"


# ---------- monolith mode ----------


def test_monolith_runs_full_pipeline_and_returns_success_result() -> None:
    runner = _runner()

    result = runner.execute(_raw_for(_valid_contract_dict()))

    assert result.status == "ok"
    assert result.error is None
    assert result.receipts is not None
    assert "result_json" in result.receipts.by_role


def test_monolith_writes_compute_output_to_storage() -> None:
    storage = _ok_storage()
    runner = _runner(storage=storage)

    runner.execute(_raw_for(_valid_contract_dict()))

    written = storage._objects["gs://gbt-storage-grabatus/user_999/out.json"]
    assert written == b"forecast-bytes"


def test_monolith_calls_webhook_with_success_payload() -> None:
    webhook = RecordingWebhookNotifier()
    runner = _runner(webhook=webhook)

    runner.execute(_raw_for(_valid_contract_dict()))

    assert len(webhook.calls) == 1
    payload = webhook.calls[0].payload
    assert payload["status"] == "ok"
    assert payload["outputs"][0]["role"] == "result_json"
    assert payload["metadata"]["model"] == "prophet"


def test_monolith_returns_error_result_when_compute_fails() -> None:
    failing = MagicMock()
    failing.run.side_effect = ComputeError("backend down")
    failing.REQUIRED_INPUT_ROLES = frozenset({"timeseries"})
    failing.OPTIONAL_INPUT_ROLES = frozenset()
    failing.OUTPUT_ROLES = frozenset({"result_json"})
    runner = _runner(compute=failing)

    result = runner.execute(_raw_for(_valid_contract_dict()))

    assert result.status == "error"
    assert isinstance(result.error, ComputeError)
    assert result.receipts is None


def test_monolith_does_not_call_webhook_when_storage_write_fails() -> None:
    failing_storage = MagicMock()
    failing_storage.read.return_value = b"raw"
    failing_storage.write.side_effect = OutputWriteError("disk full")
    webhook = RecordingWebhookNotifier()
    runner = _runner(storage=failing_storage, webhook=webhook)

    result = runner.execute(_raw_for(_valid_contract_dict()))

    assert result.status == "error"
    assert webhook.calls == []


def test_monolith_records_error_metric_on_failure() -> None:
    obs = MagicMock()
    obs.span.return_value.__enter__ = MagicMock(return_value=None)
    obs.span.return_value.__exit__ = MagicMock(return_value=False)
    failing = MagicMock()
    failing.run.side_effect = ComputeError("boom")
    failing.REQUIRED_INPUT_ROLES = frozenset({"timeseries"})
    failing.OPTIONAL_INPUT_ROLES = frozenset()
    failing.OUTPUT_ROLES = frozenset({"result_json"})
    runner = _runner(observability=obs, compute=failing)

    runner.execute(_raw_for(_valid_contract_dict()))

    obs.metric.assert_called_with(
        "service_runner.errors",
        1.0,
        error_code="compute_failed",
        mode="monolith",
    )


def test_monolith_invokes_observability_span_with_mode_tag() -> None:
    obs = MagicMock()
    obs.span.return_value.__enter__ = MagicMock(return_value=None)
    obs.span.return_value.__exit__ = MagicMock(return_value=False)
    runner = _runner(observability=obs)

    runner.execute(_raw_for(_valid_contract_dict()))

    obs.span.assert_called_with("service_runner.execute", mode="monolith")


# ---------- role compatibility ----------


def test_role_check_rejects_contract_missing_required_input_role() -> None:
    backend_two_inputs = make_fake_compute_backend(
        required_input_roles=frozenset({"timeseries", "holidays"}),
        output_roles=frozenset({"result_json"}),
        outputs={"result_json": b"x"},
    )
    runner = _runner(compute=backend_two_inputs)

    result = runner.execute(_raw_for(_valid_contract_dict()))

    assert result.status == "error"
    assert isinstance(result.error, InvalidContractError)
    assert "missing required input roles" in str(result.error)


def test_role_check_rejects_contract_with_unknown_input_role() -> None:
    contract_dict = make_contract(
        parameters=_Params(),
        inputs=[
            make_input_spec(),  # role=timeseries (required)
            make_input_spec(
                role="something_unknown",
                source_uri="gs://gbt-storage-grabatus/user_999/extra.xlsx",
            ),
        ],
    ).model_dump(mode="json")
    runner = _runner()

    result = runner.execute(_raw_for(contract_dict))

    assert result.status == "error"
    assert isinstance(result.error, InvalidContractError)
    assert "unknown input roles" in str(result.error)


def test_role_check_rejects_contract_with_mismatched_output_roles() -> None:
    contract_dict = make_contract(
        parameters=_Params(),
        outputs=[make_output_spec(role="something_else")],
    ).model_dump(mode="json")
    runner = _runner()

    result = runner.execute(_raw_for(contract_dict))

    assert result.status == "error"
    assert isinstance(result.error, InvalidContractError)
    assert "output roles" in str(result.error)


# ---------- receiver mode ----------


def test_receiver_mode_dispatches_to_configured_worker_job_name() -> None:
    dispatcher = InMemoryJobDispatcher()
    runner = _runner(
        mode=RuntimeMode.RECEIVER,
        worker_job_name="forecast-worker",
        job_dispatcher=dispatcher,
    )

    result = runner.execute(_raw_for(_valid_contract_dict()))

    assert result.status == "ok"
    assert result.receipts is None
    assert result.webhook_ack is None
    assert result.metadata["dispatched_job_id"] == "in-memory-0001"
    assert dispatcher.dispatched[0].job_name == "forecast-worker"


def test_receiver_mode_includes_validated_contract_bytes_in_dispatch() -> None:
    dispatcher = InMemoryJobDispatcher()
    runner = _runner(
        mode=RuntimeMode.RECEIVER,
        worker_job_name="forecast-worker",
        job_dispatcher=dispatcher,
    )

    runner.execute(_raw_for(_valid_contract_dict()))

    dispatched_payload = json.loads(dispatcher.dispatched[0].payload)
    assert dispatched_payload["envelope"]["protocol_version"] == "1.0"
    assert dispatched_payload["parameters"]["horizon"] == 30


def test_receiver_mode_does_not_invoke_compute() -> None:
    compute = MagicMock()
    compute.REQUIRED_INPUT_ROLES = frozenset({"timeseries"})
    compute.OPTIONAL_INPUT_ROLES = frozenset()
    compute.OUTPUT_ROLES = frozenset({"result_json"})
    runner = _runner(
        mode=RuntimeMode.RECEIVER,
        worker_job_name="forecast-worker",
        compute=compute,
    )

    runner.execute(_raw_for(_valid_contract_dict()))

    compute.run.assert_not_called()


def test_receiver_mode_returns_error_when_validation_fails() -> None:
    runner = _runner(mode=RuntimeMode.RECEIVER, worker_job_name="forecast-worker")
    bad_payload = _valid_contract_dict()
    del bad_payload["envelope"]

    result = runner.execute(_raw_for(bad_payload))

    assert result.status == "error"
    assert isinstance(result.error, InvalidContractError)


# ---------- worker mode ----------


def test_worker_mode_runs_full_pipeline_like_monolith() -> None:
    runner = _runner(mode=RuntimeMode.WORKER)

    result = runner.execute(_raw_for(_valid_contract_dict()))

    assert result.status == "ok"
    assert result.receipts is not None


def test_a_backend_that_emits_no_readout_fails_before_anything_is_written() -> None:
    storage = _ok_storage()
    runner = _runner(
        compute=make_fake_compute_backend(
            required_input_roles=frozenset({"timeseries"}),
            output_roles=frozenset({"result_json"}),
            outputs={"result_json": b"forecast-bytes"},
            emit_readout=False,
        ),
        storage=storage,
    )

    result = runner.execute(_raw_for(_valid_contract_dict()))

    assert result.status == "error"
    assert isinstance(result.error, MissingReadoutError)
    # The gate sits before save_outputs: the declared output was never written.
    with pytest.raises(InputNotFoundError):
        storage.read(
            spec=make_input_spec(source_uri="gs://gbt-storage-grabatus/user_999/out.json"),
            credentials=Credentials(token=b"", token_type="none"),
        )


def test_direct_construction_in_receiver_mode_without_worker_job_name_raises() -> None:
    # build_runner enforces worker_job_name in RECEIVER mode, but a caller
    # that bypasses build_runner and constructs ServiceRunner directly hits
    # a defense-in-depth ValueError when execute() runs the receiver path.
    template = _runner(mode=RuntimeMode.RECEIVER, worker_job_name="x")
    bad_runner: ServiceRunner[_Params] = ServiceRunner(
        contract_type=template.contract_type,
        storage=template.storage,
        message=template.message,
        webhook=template.webhook,
        compute=template.compute,
        secrets=template.secrets,
        authorizer=template.authorizer,
        observability=template.observability,
        clock=template.clock,
        job_dispatcher=template.job_dispatcher,
        scheme_allowlist=template.scheme_allowlist,
        mode=RuntimeMode.RECEIVER,
        worker_job_name=None,
    )

    with pytest.raises(ValueError, match="worker_job_name"):
        bad_runner.execute(_raw_for(_valid_contract_dict()))
