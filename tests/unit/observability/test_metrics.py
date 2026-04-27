"""Tests for the metric name catalogue."""

from __future__ import annotations

from grabatus_service_core.observability import metrics


def test_all_metric_names_use_grabatus_namespace() -> None:
    for name in metrics.ALL_METRIC_NAMES:
        assert name.startswith("grabatus.")


def test_catalogue_covers_spec_required_metrics() -> None:
    assert metrics.REQUESTS_TOTAL == "grabatus.requests.total"
    assert metrics.REQUEST_DURATION == "grabatus.request.duration"
    assert metrics.COMPUTE_DURATION == "grabatus.compute.duration"
    assert metrics.STORAGE_BYTES_READ == "grabatus.storage.bytes_read"
    assert metrics.STORAGE_BYTES_WRITTEN == "grabatus.storage.bytes_written"
    assert metrics.WEBHOOK_FAILURES == "grabatus.webhook.failures"
    assert metrics.CIRCUIT_BREAKER_STATE == "grabatus.circuit_breaker.state"


def test_all_metric_names_unique() -> None:
    assert len(set(metrics.ALL_METRIC_NAMES)) == len(metrics.ALL_METRIC_NAMES)
