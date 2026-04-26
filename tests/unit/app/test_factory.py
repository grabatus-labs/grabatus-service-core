"""Tests for build_app(): the FastAPI factory that mounts the runner."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from grabatus_service_core.app import build_app
from grabatus_service_core.contract.base import BaseServiceContract
from grabatus_service_core.runner import RuntimeMode, ServiceRunner, build_runner
from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist
from grabatus_service_core.testing import (
    AllowAllPolicy,
    FrozenClock,
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


def _runner(**overrides: Any) -> ServiceRunner[_Params]:
    defaults: dict[str, Any] = {
        "contract_type": BaseServiceContract[_Params],
        "storage": InMemoryStorage(seed={}),
        "message": InMemoryMessagePort(),
        "webhook": RecordingWebhookNotifier(),
        "compute": make_fake_compute_backend(
            required_input_roles=frozenset({"timeseries"}),
            output_roles=frozenset({"result_json"}),
            outputs={"result_json": b"x"},
        ),
        "secrets": InMemorySecretsAdapter(seed={}),
        "authorizer": AllowAllPolicy(),
        "observability": NullObservability(),
        "clock": FrozenClock(iso_string="2026-04-26T00:00:00Z"),
        "job_dispatcher": InMemoryJobDispatcher(),
        "scheme_allowlist": SchemeAllowlist(allowed={"gs"}),
        "mode": RuntimeMode.MONOLITH,
    }
    defaults.update(overrides)
    return build_runner(**defaults)


def test_build_app_returns_fastapi_instance() -> None:
    app = build_app(runner=_runner(), observability=NullObservability())

    assert isinstance(app, FastAPI)


def test_build_app_attaches_runner_for_introspection() -> None:
    runner = _runner()

    app = build_app(runner=runner, observability=NullObservability())

    assert app.state.runner is runner


def test_build_app_responds_to_health_live() -> None:
    app = build_app(runner=_runner(), observability=NullObservability())
    client = TestClient(app)

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
