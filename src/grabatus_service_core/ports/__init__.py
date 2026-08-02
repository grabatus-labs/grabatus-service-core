"""Protocol definitions (Ports) for hexagonal collaborators."""

from grabatus_service_core.ports.authorization import UriAuthorizationPort
from grabatus_service_core.ports.clock import ClockPort
from grabatus_service_core.ports.compute import ComputeBackendPort
from grabatus_service_core.ports.compute_context import ComputeContext
from grabatus_service_core.ports.job_dispatcher import (
    DispatchedJob,
    JobDispatcherPort,
)
from grabatus_service_core.ports.message import MessagePort
from grabatus_service_core.ports.observability import ObservabilityPort
from grabatus_service_core.ports.secrets import SecretsPort
from grabatus_service_core.ports.storage import StoragePort
from grabatus_service_core.ports.values import (
    ComputeResult,
    Credentials,
    LoadedInputs,
    RawMessage,
    WebhookAck,
    WriteReceipt,
)
from grabatus_service_core.ports.webhook import WebhookPort

__all__ = [
    "ClockPort",
    "ComputeBackendPort",
    "ComputeContext",
    "ComputeResult",
    "Credentials",
    "DispatchedJob",
    "JobDispatcherPort",
    "LoadedInputs",
    "MessagePort",
    "ObservabilityPort",
    "RawMessage",
    "SecretsPort",
    "StoragePort",
    "UriAuthorizationPort",
    "WebhookAck",
    "WebhookPort",
    "WriteReceipt",
]
