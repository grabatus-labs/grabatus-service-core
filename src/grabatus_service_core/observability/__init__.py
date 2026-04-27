"""Observability primitives: structlog config, OTel setup, metric catalog."""

from grabatus_service_core.observability.logging import configure_structlog
from grabatus_service_core.observability.otel_setup import (
    OpenTelemetryHandle,
    setup_opentelemetry,
)

__all__ = [
    "OpenTelemetryHandle",
    "configure_structlog",
    "setup_opentelemetry",
]
