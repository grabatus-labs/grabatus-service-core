"""OpenTelemetryObservability: adapter implementing ObservabilityPort over OTel.

Logs are recorded as span events (so Cloud Trace shows them inline with
the trace timeline). Metrics are routed through cached counters/histograms
keyed by metric name; the adapter infers the instrument type from the
metric name suffix:

- ``*.total`` and ``*.failures`` → Counter
- ``*.duration`` and ``*.bytes_*`` → Histogram
- otherwise → ObservableGauge (recorded via Counter snapshots)
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from opentelemetry import trace as otel_trace

if TYPE_CHECKING:
    from collections.abc import Iterator

    from opentelemetry.metrics import Counter, Histogram, Meter
    from opentelemetry.trace import Tracer


class OpenTelemetryObservability:
    """ObservabilityPort routed to a real OTel tracer and meter."""

    def __init__(self, *, tracer: Tracer, meter: Meter) -> None:
        self._tracer = tracer
        self._meter = meter
        self._counters: dict[str, Counter] = {}
        self._histograms: dict[str, Histogram] = {}

    def log(self, event: str, **fields: Any) -> None:  # noqa: ANN401
        span = otel_trace.get_current_span()
        if span is None or not span.is_recording():
            return
        span.add_event(event, attributes=fields)

    @contextmanager
    def span(self, name: str, **attrs: Any) -> Iterator[None]:  # noqa: ANN401
        with self._tracer.start_as_current_span(name, attributes=attrs):
            yield None

    def metric(self, name: str, value: float, **tags: Any) -> None:  # noqa: ANN401
        if name.endswith((".total", ".failures")):
            counter = self._counters.get(name) or self._meter.create_counter(name)
            self._counters[name] = counter
            counter.add(value, attributes=tags)
            return
        histogram = self._histograms.get(name) or self._meter.create_histogram(name)
        self._histograms[name] = histogram
        histogram.record(value, attributes=tags)
