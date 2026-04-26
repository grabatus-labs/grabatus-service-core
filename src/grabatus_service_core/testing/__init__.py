"""Public test fakes and factories. Imported by every downstream service test."""

from grabatus_service_core.testing.authorization import AllowAllPolicy
from grabatus_service_core.testing.clock import FrozenClock
from grabatus_service_core.testing.compute import (
    FakeComputeBackend,
    make_fake_compute_backend,
)
from grabatus_service_core.testing.factories import (
    make_callback,
    make_contract,
    make_envelope,
    make_identity,
    make_input_spec,
    make_output_spec,
    make_references,
    make_service_descriptor,
)
from grabatus_service_core.testing.job_dispatcher import (
    InMemoryJobDispatcher,
    RecordedDispatch,
)
from grabatus_service_core.testing.message import InMemoryMessagePort
from grabatus_service_core.testing.observability import NullObservability
from grabatus_service_core.testing.secrets import InMemorySecretsAdapter
from grabatus_service_core.testing.storage import InMemoryStorage
from grabatus_service_core.testing.webhook import (
    RecordedWebhookCall,
    RecordingWebhookNotifier,
)

__all__ = [
    "AllowAllPolicy",
    "FakeComputeBackend",
    "FrozenClock",
    "InMemoryJobDispatcher",
    "InMemoryMessagePort",
    "InMemorySecretsAdapter",
    "InMemoryStorage",
    "NullObservability",
    "RecordedDispatch",
    "RecordedWebhookCall",
    "RecordingWebhookNotifier",
    "make_callback",
    "make_contract",
    "make_envelope",
    "make_fake_compute_backend",
    "make_identity",
    "make_input_spec",
    "make_output_spec",
    "make_references",
    "make_service_descriptor",
]
