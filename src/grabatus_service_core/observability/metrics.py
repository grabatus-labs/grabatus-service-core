"""Canonical metric names emitted by grabatus_service_core.

Every emit site MUST use these constants — never a literal string.
Cloud Monitoring dashboards and alerting policies are defined against
these exact names; renaming requires a migration.
"""

from __future__ import annotations

from typing import Final

REQUESTS_TOTAL: Final[str] = "grabatus.requests.total"
REQUEST_DURATION: Final[str] = "grabatus.request.duration"
COMPUTE_DURATION: Final[str] = "grabatus.compute.duration"
STORAGE_BYTES_READ: Final[str] = "grabatus.storage.bytes_read"
STORAGE_BYTES_WRITTEN: Final[str] = "grabatus.storage.bytes_written"
WEBHOOK_FAILURES: Final[str] = "grabatus.webhook.failures"
CIRCUIT_BREAKER_STATE: Final[str] = "grabatus.circuit_breaker.state"

ALL_METRIC_NAMES: Final[tuple[str, ...]] = (
    REQUESTS_TOTAL,
    REQUEST_DURATION,
    COMPUTE_DURATION,
    STORAGE_BYTES_READ,
    STORAGE_BYTES_WRITTEN,
    WEBHOOK_FAILURES,
    CIRCUIT_BREAKER_STATE,
)
