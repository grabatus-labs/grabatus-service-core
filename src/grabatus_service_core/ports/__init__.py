"""Protocol definitions (Ports) for hexagonal collaborators."""

from grabatus_service_core.ports.clock import ClockPort
from grabatus_service_core.ports.job_dispatcher import (
    DispatchedJob,
    JobDispatcherPort,
)
from grabatus_service_core.ports.observability import ObservabilityPort

__all__ = [
    "ClockPort",
    "DispatchedJob",
    "JobDispatcherPort",
    "ObservabilityPort",
]
