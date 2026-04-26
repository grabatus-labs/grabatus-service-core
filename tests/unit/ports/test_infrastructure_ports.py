"""Shape tests for infrastructure Ports (Clock, Observability, JobDispatcher)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from grabatus_service_core.ports.clock import ClockPort
from grabatus_service_core.ports.job_dispatcher import (
    DispatchedJob,
    JobDispatcherPort,
)
from grabatus_service_core.ports.observability import ObservabilityPort


class _OkClock:
    def now(self) -> datetime:
        return datetime(2026, 4, 25, tzinfo=UTC)

    def monotonic(self) -> float:
        return 0.0


class _BadClock:
    def now(self) -> datetime:
        return datetime(2026, 4, 25, tzinfo=UTC)


class _OkObservability:
    def log(self, event: str, **fields: Any) -> None: ...
    def span(self, name: str, **attrs: Any) -> object:
        return object()

    def metric(self, name: str, value: float, **tags: Any) -> None: ...


class _BadObservability:
    def log(self, event: str, **fields: Any) -> None: ...


class _OkDispatcher:
    def dispatch(
        self,
        *,
        job_name: str,
        payload: bytes,
        request_id: UUID,
    ) -> DispatchedJob:
        return DispatchedJob(job_id="abc", request_id=request_id)


def test_clock_port_accepts_full_implementation() -> None:
    assert isinstance(_OkClock(), ClockPort)


def test_clock_port_rejects_missing_monotonic() -> None:
    assert not isinstance(_BadClock(), ClockPort)


def test_observability_port_accepts_full_implementation() -> None:
    assert isinstance(_OkObservability(), ObservabilityPort)


def test_observability_port_rejects_missing_method() -> None:
    assert not isinstance(_BadObservability(), ObservabilityPort)


def test_job_dispatcher_port_accepts_full_implementation() -> None:
    assert isinstance(_OkDispatcher(), JobDispatcherPort)


def test_dispatched_job_carries_job_id_and_request_id() -> None:
    rid = UUID("a3f9c21e-bf38-4e75-9a2f-c89b6c3f2d12")
    job = DispatchedJob(job_id="job-1", request_id=rid)

    assert job.job_id == "job-1"
    assert job.request_id == rid
