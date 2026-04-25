"""Errors raised by the compute backend."""

from __future__ import annotations

from grabatus_service_core.errors.base import GrabatusServiceError


class ComputeError(GrabatusServiceError):
    """Base for compute failures."""

    error_code = "compute_failed"
    http_status = 200
    retriable = False


class ComputeTimeoutError(ComputeError):
    """Compute exceeded GBT_COMPUTE_TIMEOUT_SECONDS."""

    error_code = "compute_timeout"
