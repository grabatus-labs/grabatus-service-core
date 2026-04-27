"""Bootstrap factories: turn Settings + compute + adapters into an app/runner."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from grabatus_service_core.adapters.clock import SystemClock
from grabatus_service_core.app import build_app
from grabatus_service_core.runner import RuntimeMode as RunnerMode
from grabatus_service_core.runner import ServiceRunner, build_runner
from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist

if TYPE_CHECKING:
    from fastapi import FastAPI

    from grabatus_service_core.contract.base import BaseServiceContract, ParamsT
    from grabatus_service_core.ports.compute import ComputeBackendPort
    from grabatus_service_core.settings import Settings


def build_receiver_app(
    *,
    settings: Settings,
    contract_type: type[BaseServiceContract[ParamsT]],
    compute: ComputeBackendPort,
    adapters: dict[str, Any],
) -> FastAPI:
    """Build a receiver-mode FastAPI app from settings + adapters."""
    if settings.worker_job_name is None:
        raise ValueError(
            "build_receiver_app: settings.worker_job_name is required when "
            "runtime_mode=RECEIVER (set GBT_WORKER_JOB_NAME)",
        )
    runner = _build_runner(
        settings=settings,
        contract_type=contract_type,
        compute=compute,
        adapters=adapters,
        mode=RunnerMode.RECEIVER,
    )
    return build_app(runner=runner, observability=adapters["observability"])


def build_worker_runner(
    *,
    settings: Settings,
    contract_type: type[BaseServiceContract[ParamsT]],
    compute: ComputeBackendPort,
    adapters: dict[str, Any],
) -> ServiceRunner[ParamsT]:
    """Build a worker-mode ``ServiceRunner`` (no FastAPI; CLI-driven)."""
    return _build_runner(
        settings=settings,
        contract_type=contract_type,
        compute=compute,
        adapters=adapters,
        mode=RunnerMode.WORKER,
    )


def build_monolith_app(
    *,
    settings: Settings,
    contract_type: type[BaseServiceContract[ParamsT]],
    compute: ComputeBackendPort,
    adapters: dict[str, Any],
) -> FastAPI:
    """Build a monolith-mode FastAPI app (receiver+worker fused)."""
    runner = _build_runner(
        settings=settings,
        contract_type=contract_type,
        compute=compute,
        adapters=adapters,
        mode=RunnerMode.MONOLITH,
    )
    return build_app(runner=runner, observability=adapters["observability"])


def _build_runner(
    *,
    settings: Settings,
    contract_type: type[BaseServiceContract[ParamsT]],
    compute: ComputeBackendPort,
    adapters: dict[str, Any],
    mode: RunnerMode,
) -> ServiceRunner[ParamsT]:
    return build_runner(
        contract_type=contract_type,
        storage=adapters["storage"],
        message=adapters["message"],
        webhook=adapters["webhook"],
        compute=compute,
        secrets=adapters["secrets"],
        authorizer=adapters["authorizer"],
        observability=adapters["observability"],
        clock=adapters.get("clock") or SystemClock(),
        job_dispatcher=adapters["job_dispatcher"],
        scheme_allowlist=SchemeAllowlist(allowed=set(settings.allowed_schemes)),
        mode=mode,
        worker_job_name=settings.worker_job_name,
    )
