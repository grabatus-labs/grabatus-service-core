"""End-to-end shared receiver: HTTP push -> dispatch."""

from __future__ import annotations

import json
from base64 import b64encode
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient

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

if TYPE_CHECKING:
    from fastapi import FastAPI

    from grabatus_service_core.contract.base import BaseServiceContract
    from grabatus_service_core.contract.opaque import OpaqueParameters


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "shared-receiver")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "test")
    monkeypatch.setenv(
        "GBT_SERVICE_REGISTRY",
        "forecast:grabatus-forecasting-worker,abtest:grabatus-abtest-worker",
    )
    settings = Settings()
    return build_shared_receiver_app(
        settings=settings,
        adapters=SharedReceiverAdapters(
            message=PubSubMessagePort(),
            authorizer=AllowAllPolicy(),
            job_dispatcher=InMemoryJobDispatcher(),
            observability=NullObservability(),
            clock=FrozenClock(iso_string="2026-04-27T12:00:00Z"),
        ),
    )


def _build_pubsub_payload(contract: BaseServiceContract[OpaqueParameters]) -> dict[str, Any]:
    return {
        "message": {
            "data": b64encode(
                json.dumps(contract.model_dump(mode="json")).encode("utf-8"),
            ).decode("ascii"),
        },
    }


def test_e2e_forecast_envelope_dispatches_to_forecast_worker(app: FastAPI) -> None:
    client = TestClient(app)
    contract = make_opaque_contract(parameters={"x": 1}, service_name="forecast")

    response = client.post("/run_service", json=_build_pubsub_payload(contract))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    dispatcher = app.state.runner.adapters.job_dispatcher
    assert dispatcher.dispatched[0].job_name == "grabatus-forecasting-worker"


def test_e2e_abtest_envelope_dispatches_to_abtest_worker(app: FastAPI) -> None:
    client = TestClient(app)
    contract = make_opaque_contract(parameters={"x": 1}, service_name="abtest")

    response = client.post("/run_service", json=_build_pubsub_payload(contract))

    assert response.status_code == 200
    dispatcher = app.state.runner.adapters.job_dispatcher
    assert dispatcher.dispatched[0].job_name == "grabatus-abtest-worker"


def test_e2e_unknown_service_is_rejected_gracefully(app: FastAPI) -> None:
    client = TestClient(app)
    contract = make_opaque_contract(parameters={"x": 1}, service_name="ghost")

    response = client.post("/run_service", json=_build_pubsub_payload(contract))

    assert response.status_code == 200  # Pub/Sub ack — do not retry
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["error_code"] == "unknown_service"
