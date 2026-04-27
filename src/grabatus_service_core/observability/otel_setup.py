"""Boot OpenTelemetry SDK with optional Cloud Trace + Cloud Monitoring exporters.

The Cloud exporters are imported lazily so the library remains usable on
machines (and in tests) without ``opentelemetry-exporter-gcp-*`` installed.
``setup_opentelemetry`` returns a handle whose ``shutdown()`` flushes and
disposes both providers; calling shutdown more than once is safe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    InMemoryMetricReader,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

if TYPE_CHECKING:
    from opentelemetry.metrics import Meter
    from opentelemetry.trace import Tracer


@dataclass(frozen=True)
class OpenTelemetryHandle:
    """Owned tracer+meter+shutdown for one configured OTel pipeline."""

    tracer: Tracer
    meter: Meter
    _tracer_provider: TracerProvider
    _meter_provider: MeterProvider
    _disposed: list[bool] = field(default_factory=lambda: [False])

    def shutdown(self) -> None:
        if self._disposed[0]:
            return
        self._disposed[0] = True
        self._tracer_provider.shutdown()
        self._meter_provider.shutdown()


def setup_opentelemetry(
    *,
    env: Literal["local", "staging", "production"],
    sample_rate: float,
) -> OpenTelemetryHandle:
    """Return an :class:`OpenTelemetryHandle` configured for ``env``."""
    sampler = TraceIdRatioBased(sample_rate)
    tracer_provider = TracerProvider(sampler=sampler)

    cloud_trace_cls = _load_cloud_trace_exporter() if env == "production" else None
    if cloud_trace_cls is not None:
        tracer_provider.add_span_processor(BatchSpanProcessor(cloud_trace_cls()))
    else:
        tracer_provider.add_span_processor(SimpleSpanProcessor(InMemorySpanExporter()))

    cloud_monitoring_cls = _load_cloud_monitoring_exporter() if env == "production" else None
    if cloud_monitoring_cls is not None:
        meter_provider = MeterProvider(
            metric_readers=[PeriodicExportingMetricReader(cloud_monitoring_cls())],
        )
    else:
        meter_provider = MeterProvider(metric_readers=[InMemoryMetricReader()])

    return OpenTelemetryHandle(
        tracer=tracer_provider.get_tracer("grabatus_service_core"),
        meter=meter_provider.get_meter("grabatus_service_core"),
        _tracer_provider=tracer_provider,
        _meter_provider=meter_provider,
    )


def _load_cloud_trace_exporter() -> type | None:  # pragma: no cover  # via monkeypatch
    try:
        from opentelemetry.exporter.cloud_trace import (  # noqa: PLC0415
            CloudTraceSpanExporter,
        )
    except ImportError:
        return None
    return CloudTraceSpanExporter  # type: ignore[no-any-return]


def _load_cloud_monitoring_exporter() -> type | None:  # pragma: no cover  # via monkeypatch
    try:
        from opentelemetry.exporter.cloud_monitoring import (  # noqa: PLC0415
            CloudMonitoringMetricsExporter,
        )
    except ImportError:
        return None
    return CloudMonitoringMetricsExporter  # type: ignore[no-any-return]
