"""Tests for StructlogObservability."""

from __future__ import annotations

import structlog
from structlog.testing import LogCapture

from grabatus_service_core.adapters.observability import StructlogObservability
from grabatus_service_core.ports.observability import ObservabilityPort


def _capture() -> tuple[LogCapture, StructlogObservability]:
    log_capture = LogCapture()
    structlog.configure(processors=[log_capture])
    return log_capture, StructlogObservability()


def test_structlog_observability_satisfies_port() -> None:
    assert isinstance(StructlogObservability(), ObservabilityPort)


def test_log_emits_event_with_named_fields() -> None:
    capture, obs = _capture()

    obs.log("upload_received", user_id="999", file_size=1234)

    assert capture.entries[0]["event"] == "upload_received"
    assert capture.entries[0]["user_id"] == "999"
    assert capture.entries[0]["file_size"] == 1234


def test_metric_emits_log_with_metric_marker_and_value() -> None:
    capture, obs = _capture()

    obs.metric("forecast_duration_seconds", 12.5, service="forecast")

    entry = capture.entries[0]
    assert entry["event"] == "metric"
    assert entry["metric_name"] == "forecast_duration_seconds"
    assert entry["metric_value"] == 12.5
    assert entry["service"] == "forecast"


def test_span_yields_none_and_emits_start_end() -> None:
    capture, obs = _capture()

    with obs.span("decode", request_id="r1") as scope:
        assert scope is None

    events = [e["event"] for e in capture.entries]
    assert events == ["span_start", "span_end"]
    assert capture.entries[0]["span"] == "decode"
    assert capture.entries[0]["request_id"] == "r1"


def test_span_emits_end_even_when_body_raises() -> None:
    capture, obs = _capture()

    try:
        with obs.span("crashy"):
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    events = [e["event"] for e in capture.entries]
    assert events == ["span_start", "span_end"]
