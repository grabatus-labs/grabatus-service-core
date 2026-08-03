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


class UnknownOutputRoleError(ComputeError):
    """The backend asked the context for a role the contract does not declare.

    Raised only by a service bug — a typo, or a role the backend forgot to
    list in ``OUTPUT_ROLES``. Typed rather than a bare ``KeyError`` so the
    runner reports it as a run failure instead of killing the worker.
    """

    error_code = "unknown_output_role"


class ReadoutMismatchError(ComputeError):
    """The readout is schema-valid but describes a different run.

    Distinct from ``invalid_model_readout`` because the cause differs: the
    schema error is a bug in how the service builds the artifact, this one
    means the artifact belongs to another request — a cached or copied
    readout that would explain the wrong numbers to the client.
    """

    error_code = "readout_identity_mismatch"
