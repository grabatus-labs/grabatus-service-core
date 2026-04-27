"""Tests for POST /run_service: Pub/Sub push handler."""

from __future__ import annotations

import base64
import json
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from grabatus_service_core.adapters.message_pubsub import PubSubMessagePort
from grabatus_service_core.app import build_app
from grabatus_service_core.contract.base import BaseServiceContract
from grabatus_service_core.contract.opaque import OpaqueParameters
from grabatus_service_core.receiver.registry import ServiceRegistry
from grabatus_service_core.receiver.runner import SharedReceiverAdapters, SharedReceiverRunner
from grabatus_service_core.runner import RuntimeMode, ServiceRunner, build_runner
from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist
from grabatus_service_core.testing import (
    AllowAllPolicy,
    FrozenClock,
    InMemoryJobDispatcher,
    InMemorySecretsAdapter,
    InMemoryStorage,
    NullObservability,
    RecordingWebhookNotifier,
    make_contract,
    make_fake_compute_backend,
)
from grabatus_service_core.testing.factories import make_service_descriptor


class _Params(BaseModel):
    horizon: int = 30


def _seeded_storage() -> InMemoryStorage:
    return InMemoryStorage(
        seed={"gs://gbt-storage-grabatus/user_999/in.xlsx": b"raw-bytes"},
    )


def _runner(**overrides: Any) -> ServiceRunner[_Params]:
    defaults: dict[str, Any] = {
        "contract_type": BaseServiceContract[_Params],
        "storage": _seeded_storage(),
        "message": PubSubMessagePort(),
        "webhook": RecordingWebhookNotifier(),
        "compute": make_fake_compute_backend(
            required_input_roles=frozenset({"timeseries"}),
            output_roles=frozenset({"result_json"}),
            outputs={"result_json": b"forecast"},
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


def _pubsub_envelope(contract_dict: dict[str, Any]) -> dict[str, Any]:
    encoded = base64.b64encode(json.dumps(contract_dict).encode("utf-8")).decode("ascii")
    return {"message": {"data": encoded, "messageId": "1"}, "subscription": "x"}


@pytest.fixture
def client() -> TestClient:
    app = build_app(runner=_runner(), observability=NullObservability())
    return TestClient(app)


def test_run_service_returns_200_on_success(client: TestClient) -> None:
    contract = make_contract(parameters=_Params(horizon=30)).model_dump(mode="json")

    response = client.post("/run_service", json=_pubsub_envelope(contract))

    assert response.status_code == 200


def test_run_service_response_payload_contains_status_and_request_id(
    client: TestClient,
) -> None:
    contract = make_contract(parameters=_Params(horizon=30)).model_dump(mode="json")
    expected_request_id = contract["envelope"]["request_id"]

    response = client.post("/run_service", json=_pubsub_envelope(contract))
    body = response.json()

    assert body["status"] == "ok"
    UUID(body["request_id"])
    assert body["request_id"] == expected_request_id


def test_run_service_returns_200_with_error_payload_on_invalid_contract(
    client: TestClient,
) -> None:
    bad = {"message": {"data": "not-base64!!!", "messageId": "1"}, "subscription": "x"}

    response = client.post("/run_service", json=bad)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["error_code"] == "malformed_message"


def test_run_service_handles_non_json_body_with_error_payload(client: TestClient) -> None:
    response = client.post(
        "/run_service",
        content=b"not-json",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["error_code"] == "malformed_message"


def test_run_service_with_shared_receiver_runner_includes_dispatched_job_id() -> None:
    """SharedReceiverRunner result includes dispatched_job_id in the response."""
    runner = SharedReceiverRunner(
        adapters=SharedReceiverAdapters(
            message=PubSubMessagePort(),
            authorizer=AllowAllPolicy(),
            job_dispatcher=InMemoryJobDispatcher(),
            observability=NullObservability(),
            clock=FrozenClock("2026-04-27T12:00:00Z"),
        ),
        scheme_allowlist=SchemeAllowlist(allowed={"gs", "bigquery", "secret"}),
        registry=ServiceRegistry(by_name={"forecast": "grabatus-forecasting-worker"}),
    )
    app = build_app(runner=runner, observability=NullObservability())
    client = TestClient(app)

    contract = make_contract(
        parameters=OpaqueParameters.model_validate({"x": 1}),
        service=make_service_descriptor(name="forecast"),
    )
    inner_json = json.dumps(contract.model_dump(mode="json")).encode("utf-8")
    wrapper = {"message": {"data": base64.b64encode(inner_json).decode("ascii")}}
    response = client.post("/run_service", json=wrapper)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "dispatched_job_id" in body
    assert body["dispatched_job_id"] is not None
