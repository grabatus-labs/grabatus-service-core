"""InMemoryJobDispatcher: records dispatched jobs without enqueuing real work."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count
from typing import TYPE_CHECKING

from grabatus_service_core.ports.job_dispatcher import DispatchedJob

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class RecordedDispatch:
    job_name: str
    payload: bytes
    request_id: UUID


@dataclass
class InMemoryJobDispatcher:
    """Records every dispatch call; assigns sequential job IDs."""

    dispatched: list[RecordedDispatch] = field(default_factory=list)
    _counter: count[int] = field(default_factory=lambda: count(1))

    def dispatch(
        self,
        *,
        job_name: str,
        payload: bytes,
        request_id: UUID,
    ) -> DispatchedJob:
        self.dispatched.append(
            RecordedDispatch(
                job_name=job_name,
                payload=payload,
                request_id=request_id,
            ),
        )
        seq = next(self._counter)
        return DispatchedJob(job_id=f"in-memory-{seq:04d}", request_id=request_id)
