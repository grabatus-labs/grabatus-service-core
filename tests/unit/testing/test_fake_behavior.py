"""Behavior tests: each fake delivers what its docstring promises."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

import pytest

from grabatus_service_core.contract.callback import Callback
from grabatus_service_core.contract.identity import Identity
from grabatus_service_core.contract.io_spec import InputSpec, OutputSpec
from grabatus_service_core.contract.readout.enums import READOUT_OUTPUT_ROLE
from grabatus_service_core.contract.secret_ref import SecretRef
from grabatus_service_core.errors import (
    CredentialResolutionError,
    InputNotFoundError,
    UnsupportedSchemeError,
)
from grabatus_service_core.ports.values import (
    Credentials,
    LoadedInputs,
    RawMessage,
)
from grabatus_service_core.testing import (
    AllowAllPolicy,
    FrozenClock,
    InMemoryJobDispatcher,
    InMemoryMessagePort,
    InMemorySecretsAdapter,
    InMemoryStorage,
    NullObservability,
    RecordingWebhookNotifier,
    make_compute_context,
    make_fake_compute_backend,
)


def _input(role: str = "timeseries", uri: str = "gs://b/in.xlsx") -> InputSpec:
    return InputSpec.model_validate(
        {
            "role": role,
            "source_uri": uri,
            "format": "xlsx",
            "format_hints": {"format": "xlsx"},
        },
    )


def _output(role: str = "result", uri: str = "gs://b/out.json") -> OutputSpec:
    return OutputSpec.model_validate(
        {
            "role": role,
            "destination_uri": uri,
            "format": "json",
            "format_hints": {"format": "json"},
        },
    )


def _empty_creds() -> Credentials:
    return Credentials(token=b"", token_type="bearer")


def test_frozen_clock_returns_configured_time() -> None:
    clock = FrozenClock("2026-04-25T12:00:00Z")

    assert clock.now() == datetime(2026, 4, 25, 12, 0, 0, tzinfo=UTC)
    assert clock.monotonic() == 0.0


def test_frozen_clock_advance_changes_now_and_monotonic() -> None:
    clock = FrozenClock("2026-04-25T12:00:00Z")

    clock.advance(seconds=30)

    assert clock.now() == datetime(2026, 4, 25, 12, 0, 30, tzinfo=UTC)
    assert clock.monotonic() == 30.0


def test_null_observability_records_nothing_but_is_callable() -> None:
    obs = NullObservability()

    obs.log("event", x=1)
    obs.metric("m", 1.0, tag="v")
    with obs.span("span", attr="v") as span:
        assert span is None


def test_in_memory_storage_round_trips_bytes() -> None:
    storage = InMemoryStorage()
    receipt = storage.write(
        spec=_output(role="result", uri="gs://b/out.json"),
        payload=b"hello",
        credentials=_empty_creds(),
    )

    data = storage.read(
        spec=_input(role="result", uri="gs://b/out.json"),
        credentials=_empty_creds(),
    )

    assert receipt.bytes_written == 5
    assert data == b"hello"


def test_in_memory_storage_raises_for_missing_uri() -> None:
    storage = InMemoryStorage()

    with pytest.raises(InputNotFoundError, match=r"gs://b/missing"):
        storage.read(
            spec=_input(uri="gs://b/missing"),
            credentials=_empty_creds(),
        )


def test_in_memory_storage_can_be_seeded_via_constructor() -> None:
    storage = InMemoryStorage(seed={"gs://b/in.xlsx": b"seeded"})

    data = storage.read(
        spec=_input(uri="gs://b/in.xlsx"),
        credentials=_empty_creds(),
    )

    assert data == b"seeded"


def test_in_memory_message_port_round_trips_dict() -> None:
    port = InMemoryMessagePort()
    payload = {"k": "v", "n": 1}

    encoded = port.encode(payload)
    decoded = port.decode(RawMessage(payload=encoded))

    assert decoded == payload


def test_in_memory_message_port_rejects_non_dict_payload() -> None:
    port = InMemoryMessagePort()

    with pytest.raises(ValueError, match="dict"):
        port.decode(RawMessage(payload=b"[1, 2, 3]"))


def test_recording_webhook_notifier_records_every_call() -> None:
    notifier = RecordingWebhookNotifier()
    callback = Callback.model_validate(
        {"url": "https://x.com/wh", "auth_scheme": "jwt_hs256"},
    )

    ack1 = notifier.notify(callback=callback, payload={"a": 1})
    ack2 = notifier.notify(callback=callback, payload={"b": 2})

    assert ack1.http_status == 200
    assert ack2.http_status == 200
    assert len(notifier.calls) == 2
    assert notifier.calls[0].payload == {"a": 1}
    assert notifier.calls[1].payload == {"b": 2}


def test_recording_webhook_notifier_can_be_configured_to_fail() -> None:
    notifier = RecordingWebhookNotifier(default_status=503)
    callback = Callback.model_validate(
        {"url": "https://x.com/wh", "auth_scheme": "jwt_hs256"},
    )

    ack = notifier.notify(callback=callback, payload={})

    assert ack.http_status == 503


def test_fake_compute_backend_returns_configured_outputs() -> None:
    backend = make_fake_compute_backend(
        required_input_roles=frozenset({"timeseries"}),
        output_roles=frozenset({"result_json"}),
        outputs={"result_json": b"forecast-bytes"},
        metadata={"version": "1.0"},
    )

    context = make_compute_context()

    result = backend.run(
        inputs=LoadedInputs(by_role={"timeseries": b"data"}),
        parameters=None,
        context=context,
    )

    assert result.by_role["result_json"] == b"forecast-bytes"
    assert result.metadata["version"] == "1.0"
    readout = json.loads(result.by_role[READOUT_OUTPUT_ROLE])
    # The fake must stamp the run it was given, not the canned defaults:
    # anything else fails the runner's mismatch check.
    assert readout["request"]["request_id"] == context.request_id
    assert readout["service"]["name"] == context.service_name


def test_make_fake_compute_backend_isolates_role_declarations() -> None:
    backend_a = make_fake_compute_backend(
        required_input_roles=frozenset({"timeseries"}),
        output_roles=frozenset({"a_out"}),
        outputs={"a_out": b"a"},
    )
    backend_b = make_fake_compute_backend(
        required_input_roles=frozenset({"holidays"}),
        output_roles=frozenset({"b_out"}),
        outputs={"b_out": b"b"},
    )

    assert frozenset({"timeseries"}) == type(backend_a).REQUIRED_INPUT_ROLES
    assert frozenset({"holidays"}) == type(backend_b).REQUIRED_INPUT_ROLES
    assert type(backend_a) is not type(backend_b)


def test_in_memory_secrets_adapter_resolves_seeded_token() -> None:
    adapter = InMemorySecretsAdapter(
        seed={
            "secret://gsm/bq-reader/1": Credentials(
                token=b"abc123",
                token_type="bearer",
            ),
        },
    )

    creds = adapter.resolve(
        secret_ref=SecretRef.model_validate("secret://gsm/bq-reader/1"),
    )

    assert creds.token == b"abc123"


def test_in_memory_secrets_adapter_raises_for_unknown_ref() -> None:
    adapter = InMemorySecretsAdapter()

    with pytest.raises(CredentialResolutionError, match="secret"):
        adapter.resolve(
            secret_ref=SecretRef.model_validate("secret://gsm/missing/1"),
        )


def test_allow_all_policy_authorizes_anything() -> None:
    policy = AllowAllPolicy()

    policy.authorize(
        uri="gs://anything/anywhere",
        identity=Identity.model_validate({"user_id": "1", "tenant_id": "grabatus"}),
    )


def test_in_memory_job_dispatcher_records_dispatched_jobs() -> None:
    dispatcher = InMemoryJobDispatcher()
    rid = UUID("a3f9c21e-bf38-4e75-9a2f-c89b6c3f2d12")

    job = dispatcher.dispatch(job_name="worker-job", payload=b"x", request_id=rid)

    assert job.job_id.startswith("in-memory-")
    assert job.request_id == rid
    assert len(dispatcher.dispatched) == 1
    assert dispatcher.dispatched[0].payload == b"x"


def test_in_memory_storage_rejects_unsupported_scheme() -> None:
    storage = InMemoryStorage(supported_schemes=frozenset({"gs"}))

    with pytest.raises(UnsupportedSchemeError):
        storage.write(
            spec=_output(role="r", uri="ftp://b/x"),
            payload=b"x",
            credentials=_empty_creds(),
        )
