"""ObservabilityPort: structured logs, traces, and metrics."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from contextlib import AbstractContextManager


@runtime_checkable
class ObservabilityPort(Protocol):
    """Single entry point for emitting logs, spans, and metrics.

    Implementations route to structlog (logs), OpenTelemetry (spans),
    and OTel/Cloud Monitoring (metrics). Tests inject ``NullObservability``
    which records nothing.
    """

    def log(self, event: str, **fields: Any) -> None:
        """Emit a structured log event with named fields."""
        ...

    def span(self, name: str, **attrs: Any) -> AbstractContextManager[object]:
        """Return a context manager that records a tracing span."""
        ...

    def metric(self, name: str, value: float, **tags: Any) -> None:
        """Record a metric data point with tag dimensions."""
        ...
