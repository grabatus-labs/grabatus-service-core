"""Each fake must satisfy its corresponding Port via isinstance."""

from __future__ import annotations

from grabatus_service_core.ports import (
    ClockPort,
    ComputeBackendPort,
    JobDispatcherPort,
    MessagePort,
    ObservabilityPort,
    SecretsPort,
    StoragePort,
    UriAuthorizationPort,
    WebhookPort,
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
    make_fake_compute_backend,
)


def test_frozen_clock_is_clock_port() -> None:
    assert isinstance(FrozenClock("2026-04-25T12:00:00Z"), ClockPort)


def test_null_observability_is_observability_port() -> None:
    assert isinstance(NullObservability(), ObservabilityPort)


def test_in_memory_job_dispatcher_is_job_dispatcher_port() -> None:
    assert isinstance(InMemoryJobDispatcher(), JobDispatcherPort)


def test_in_memory_storage_is_storage_port() -> None:
    assert isinstance(InMemoryStorage(), StoragePort)


def test_in_memory_message_port_is_message_port() -> None:
    assert isinstance(InMemoryMessagePort(), MessagePort)


def test_recording_webhook_notifier_is_webhook_port() -> None:
    assert isinstance(RecordingWebhookNotifier(), WebhookPort)


def test_fake_compute_backend_is_compute_backend_port() -> None:
    backend = make_fake_compute_backend(
        required_input_roles=frozenset({"timeseries"}),
        output_roles=frozenset({"result"}),
        outputs={"result": b"x"},
    )
    assert isinstance(backend, ComputeBackendPort)


def test_in_memory_secrets_adapter_is_secrets_port() -> None:
    assert isinstance(InMemorySecretsAdapter(), SecretsPort)


def test_allow_all_policy_is_uri_authorization_port() -> None:
    assert isinstance(AllowAllPolicy(), UriAuthorizationPort)
