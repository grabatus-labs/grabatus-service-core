"""build_shared_receiver_app: end-to-end FastAPI wiring."""

from __future__ import annotations

import json
from base64 import b64encode

import pytest
from fastapi.testclient import TestClient

import grabatus_service_core.receiver as receiver_pkg
from grabatus_service_core.adapters.message_pubsub import PubSubMessagePort
from grabatus_service_core.receiver.app import build_shared_receiver_app
from grabatus_service_core.receiver.runner import SharedReceiverAdapters
from grabatus_service_core.settings import Settings
from grabatus_service_core.testing import (
    AllowAllPolicy,
    FrozenClock,
    InMemoryJobDispatcher,
    NullObservability,
    make_opaque_contract,
)


def _settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "shared-receiver")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "test")
    monkeypatch.setenv("GBT_SERVICE_REGISTRY", "forecast:fc-worker")
    return Settings()


def _adapters(dispatcher: InMemoryJobDispatcher) -> SharedReceiverAdapters:
    return SharedReceiverAdapters(
        message=PubSubMessagePort(),
        authorizer=AllowAllPolicy(),
        job_dispatcher=dispatcher,
        observability=NullObservability(),
        clock=FrozenClock(iso_string="2026-04-27T12:00:00Z"),
    )


def test_health_live_returns_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch)
    app = build_shared_receiver_app(settings=settings, adapters=_adapters(InMemoryJobDispatcher()))
    client = TestClient(app)

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_ready_reports_shared_receiver_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch)
    app = build_shared_receiver_app(settings=settings, adapters=_adapters(InMemoryJobDispatcher()))
    client = TestClient(app)

    response = client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["mode"] == "shared-receiver"


def test_run_service_dispatches_via_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch)
    dispatcher = InMemoryJobDispatcher()
    app = build_shared_receiver_app(settings=settings, adapters=_adapters(dispatcher))
    client = TestClient(app)

    contract = make_opaque_contract(parameters={"x": 1}, service_name="forecast")
    inner = contract.model_dump(mode="json")
    pubsub_envelope = {
        "message": {
            "data": b64encode(json.dumps(inner).encode("utf-8")).decode("ascii"),
        },
    }

    response = client.post("/run_service", json=pubsub_envelope)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "dispatched_job_id" in body
    assert len(dispatcher.dispatched) == 1
    assert dispatcher.dispatched[0].job_name == "fc-worker"


def test_receiver_package_exports_build_shared_receiver_app() -> None:
    factory = receiver_pkg.build_shared_receiver_app
    assert factory is build_shared_receiver_app


def test_receiver_package_getattr_raises_for_unknown_name() -> None:
    with pytest.raises(AttributeError, match="has no attribute"):
        receiver_pkg.__getattr__("nonexistent_symbol")
