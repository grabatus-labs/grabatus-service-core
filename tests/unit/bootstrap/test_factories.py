"""Tests for bootstrap factories."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from pydantic import BaseModel

from grabatus_service_core.bootstrap import (
    build_monolith_app,
    build_receiver_app,
    build_worker_runner,
)
from grabatus_service_core.contract.base import BaseServiceContract
from grabatus_service_core.runner import RuntimeMode, ServiceRunner
from grabatus_service_core.settings import Settings
from grabatus_service_core.testing import (
    AllowAllPolicy,
    InMemoryJobDispatcher,
    InMemoryMessagePort,
    InMemorySecretsAdapter,
    InMemoryStorage,
    NullObservability,
    RecordingWebhookNotifier,
    make_fake_compute_backend,
)


class _Params(BaseModel):
    horizon: int = 30


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "monolith")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "x")
    return Settings()


def _compute() -> Any:
    return make_fake_compute_backend(
        required_input_roles=frozenset({"timeseries"}),
        output_roles=frozenset({"result_json"}),
        outputs={"result_json": b"x"},
    )


def _adapters() -> dict[str, Any]:
    return {
        "storage": InMemoryStorage(seed={}),
        "message": InMemoryMessagePort(),
        "webhook": RecordingWebhookNotifier(),
        "secrets": InMemorySecretsAdapter(seed={}),
        "authorizer": AllowAllPolicy(),
        "observability": NullObservability(),
        "job_dispatcher": InMemoryJobDispatcher(),
    }


def test_build_monolith_app_returns_fastapi(settings: Settings) -> None:
    app = build_monolith_app(
        settings=settings,
        contract_type=BaseServiceContract[_Params],
        compute=_compute(),
        adapters=_adapters(),
    )

    assert isinstance(app, FastAPI)
    assert app.state.runner.mode is RuntimeMode.MONOLITH


def test_build_receiver_app_requires_worker_job_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "receiver")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "x")
    settings = Settings()

    with pytest.raises(ValueError, match="worker_job_name"):
        build_receiver_app(
            settings=settings,
            contract_type=BaseServiceContract[_Params],
            compute=_compute(),
            adapters=_adapters(),
        )


def test_build_receiver_app_uses_worker_job_name_from_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "receiver")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "x")
    monkeypatch.setenv("GBT_WORKER_JOB_NAME", "forecast-worker")
    settings = Settings()

    app = build_receiver_app(
        settings=settings,
        contract_type=BaseServiceContract[_Params],
        compute=_compute(),
        adapters=_adapters(),
    )

    assert app.state.runner.mode is RuntimeMode.RECEIVER
    assert app.state.runner.worker_job_name == "forecast-worker"


def test_build_worker_runner_returns_service_runner(settings: Settings) -> None:
    runner = build_worker_runner(
        settings=settings,
        contract_type=BaseServiceContract[_Params],
        compute=_compute(),
        adapters=_adapters(),
    )

    assert isinstance(runner, ServiceRunner)
    assert runner.mode is RuntimeMode.WORKER
