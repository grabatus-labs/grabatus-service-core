"""Tests for OpenTelemetryObservability."""

from __future__ import annotations

import pytest
from opentelemetry.metrics import NoOpMeter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import NoOpTracer

from grabatus_service_core.adapters.observability_otel import (
    OpenTelemetryObservability,
)


@pytest.fixture
def otel_observability() -> tuple[
    OpenTelemetryObservability, InMemorySpanExporter, InMemoryMetricReader
]:
    span_exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    metric_reader = InMemoryMetricReader()
    meter_provider = MeterProvider(metric_readers=[metric_reader])
    obs = OpenTelemetryObservability(
        tracer=tracer_provider.get_tracer("test"),
        meter=meter_provider.get_meter("test"),
    )
    return obs, span_exporter, metric_reader


def test_otel_observability_records_span_with_attributes(
    otel_observability: tuple[
        OpenTelemetryObservability, InMemorySpanExporter, InMemoryMetricReader
    ],
) -> None:
    obs, span_exporter, _ = otel_observability

    with obs.span("pipeline.step", step="decode"):
        pass

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "pipeline.step"
    assert spans[0].attributes is not None
    assert spans[0].attributes["step"] == "decode"


def test_otel_observability_records_metric_via_counter(
    otel_observability: tuple[
        OpenTelemetryObservability, InMemorySpanExporter, InMemoryMetricReader
    ],
) -> None:
    obs, _, metric_reader = otel_observability

    obs.metric("grabatus.requests.total", 1.0, status="ok", error_code="")
    obs.metric("grabatus.requests.total", 1.0, status="ok", error_code="")

    data = metric_reader.get_metrics_data()
    assert data is not None
    metric_names = [
        metric.name
        for resource_metrics in data.resource_metrics
        for scope_metrics in resource_metrics.scope_metrics
        for metric in scope_metrics.metrics
    ]
    assert "grabatus.requests.total" in metric_names


def test_otel_observability_log_emits_event_via_span_event() -> None:
    span_exporter = InMemorySpanExporter()
    tp = TracerProvider()
    tp.add_span_processor(SimpleSpanProcessor(span_exporter))
    obs = OpenTelemetryObservability(
        tracer=tp.get_tracer("test"),
        meter=NoOpMeter("test"),
    )

    with obs.span("outer"):
        obs.log("compute_started", model="prophet")

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    events = list(spans[0].events)
    assert any(e.name == "compute_started" for e in events)


def test_otel_observability_log_outside_span_is_noop() -> None:
    obs = OpenTelemetryObservability(tracer=NoOpTracer(), meter=NoOpMeter("test"))

    obs.log("orphaned_event", key="value")  # must not raise
