"""JobDispatcherPort: enqueue worker jobs from the receiver."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class DispatchedJob:
    """Outcome of dispatching a worker job."""

    job_id: str
    request_id: UUID


@runtime_checkable
class JobDispatcherPort(Protocol):
    """Hand off the validated envelope from receiver to worker.

    Implementations wrap Cloud Run Jobs (production) or in-memory queues
    (tests). The ``payload`` is the already-validated, re-serialized
    contract the worker should execute.
    """

    def dispatch(
        self,
        *,
        job_name: str,
        payload: bytes,
        request_id: UUID,
    ) -> DispatchedJob:
        """Enqueue the worker run; return a handle for log correlation."""
        ...
