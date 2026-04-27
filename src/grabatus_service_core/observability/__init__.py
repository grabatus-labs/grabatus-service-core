"""Observability primitives: structlog config, OTel setup, metric catalog."""

from grabatus_service_core.observability.logging import configure_structlog

__all__ = ["configure_structlog"]
