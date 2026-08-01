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


class MissingReadoutError(ComputeError):
    """The backend produced no ``model_readout`` role.

    Not retriable: a backend that does not emit a readout will not emit one
    on the next attempt either.
    """

    error_code = "missing_model_readout"


class InvalidReadoutError(ComputeError):
    """The ``model_readout`` produced does not satisfy the readout schema."""

    error_code = "invalid_model_readout"
