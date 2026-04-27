"""Tests for setup_opentelemetry()."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import grabatus_service_core.observability.otel_setup as otel_setup_mod
from grabatus_service_core.observability.otel_setup import setup_opentelemetry

if TYPE_CHECKING:
    import pytest


def test_setup_returns_tracer_and_meter_for_local_env() -> None:
    handle = setup_opentelemetry(env="local", sample_rate=1.0)
    try:
        with handle.tracer.start_as_current_span("test") as span:
            assert span.is_recording()
        handle.meter.create_counter("local.counter").add(1.0)
    finally:
        handle.shutdown()


def test_setup_handle_shutdown_is_idempotent() -> None:
    handle = setup_opentelemetry(env="local", sample_rate=1.0)

    handle.shutdown()
    handle.shutdown()  # second call must not raise


def test_setup_uses_cloud_trace_exporter_in_production_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Smoke test: production env path is taken; we don't actually export."""
    mod = otel_setup_mod

    captured: dict[str, object] = {}

    class _StubExporter:
        def __init__(self, *args: object, **kwargs: object) -> None:
            captured["constructed"] = True

        def export(self, spans: object) -> object:  # pragma: no cover  # not called in test
            return None

        def shutdown(self) -> None:
            return None

    monkeypatch.setattr(mod, "_load_cloud_trace_exporter", lambda: _StubExporter)
    monkeypatch.setattr(mod, "_load_cloud_monitoring_exporter", lambda: None)

    handle = setup_opentelemetry(env="production", sample_rate=0.5)
    try:
        assert captured["constructed"] is True
    finally:
        handle.shutdown()


def test_setup_falls_back_to_in_memory_when_cloud_exporter_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = otel_setup_mod

    monkeypatch.setattr(mod, "_load_cloud_trace_exporter", lambda: None)
    monkeypatch.setattr(mod, "_load_cloud_monitoring_exporter", lambda: None)

    handle = setup_opentelemetry(env="production", sample_rate=1.0)

    try:
        with handle.tracer.start_as_current_span("test") as span:
            assert span.is_recording()
    finally:
        handle.shutdown()


def test_setup_uses_cloud_monitoring_exporter_in_production_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = otel_setup_mod

    captured: dict[str, object] = {}

    class _StubMetricsExporter:
        _preferred_temporality: ClassVar[dict[type, object]] = {}
        _preferred_aggregation: ClassVar[dict[type, object]] = {}

        def __init__(self, *args: object, **kwargs: object) -> None:
            captured["constructed"] = True

        def export(self, *args: object, **kwargs: object) -> object:  # pragma: no cover
            return None

        def force_flush(self, timeout_millis: float = 0) -> bool:  # pragma: no cover
            return True

        def shutdown(self, timeout_millis: float = 0, **kwargs: object) -> None:
            return None

    monkeypatch.setattr(mod, "_load_cloud_trace_exporter", lambda: None)
    monkeypatch.setattr(mod, "_load_cloud_monitoring_exporter", lambda: _StubMetricsExporter)

    handle = setup_opentelemetry(env="production", sample_rate=1.0)
    try:
        assert captured["constructed"] is True
    finally:
        handle.shutdown()
