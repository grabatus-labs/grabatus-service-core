"""End-to-end smoke test for the forecast example service, over HTTP.

The sibling ``test_forecast_backend`` drives the same backend through the
runner directly. This one goes through the ASGI app and the Pub/Sub
envelope, so the example is exercised the way the platform calls it.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx
import pytest
from examples.forecast_service import build
from examples.forecast_service.compute import RESULT_URI

from grabatus_service_core.contract.readout.enums import READOUT_OUTPUT_ROLE

_REQUEST_ID = "11111111-1111-1111-1111-111111111111"
_READOUT_URI = "gs://gbt-storage-grabatus/user_999/readout.json"


def _output(role: str, uri: str) -> dict[str, Any]:
    return {
        "role": role,
        "destination_uri": uri,
        "format": "json",
        "format_hints": {"format": "json"},
        "compression": "none",
        "write_mode": "overwrite",
    }


def _contract() -> dict[str, Any]:
    return {
        "envelope": {
            "protocol_version": "1.1",
            "request_id": _REQUEST_ID,
            "created_at": "2026-04-26T00:00:00Z",
            "origin": "internal",
        },
        "identity": {"user_id": "999", "tenant_id": "grabatus"},
        "references": {"parameter_id": "p", "result_id": "r"},
        "service": {"name": "forecast", "version": "0.0.1"},
        "inputs": [
            {
                "role": "timeseries",
                "source_uri": "gs://gbt-storage-grabatus/user_999/history.csv",
                "format": "csv",
                "format_hints": {"format": "csv"},
            },
        ],
        "outputs": [
            _output("result_json", RESULT_URI),
            _output(READOUT_OUTPUT_ROLE, _READOUT_URI),
        ],
        "callback": {"url": "https://example.com/cb", "auth_scheme": "jwt_hs256"},
        "parameters": {"horizon": 3},
    }


def _pubsub_envelope(contract: dict[str, Any]) -> dict[str, Any]:
    encoded = base64.b64encode(json.dumps(contract).encode("utf-8")).decode("ascii")
    return {"message": {"data": encoded, "messageId": "1"}, "subscription": "x"}


async def _post_contract() -> httpx.Response:
    transport = httpx.ASGITransport(app=build())
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        return await client.post("/run_service", json=_pubsub_envelope(_contract()))


def _set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "monolith")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "test-secret")
    monkeypatch.setenv("GBT_ALLOWED_SCHEMES", "gs,https")


@pytest.mark.asyncio
async def test_forecast_service_runs_end_to_end_via_asgi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_env(monkeypatch)

    response = await _post_contract()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok", body
    assert body["request_id"] == _REQUEST_ID


@pytest.mark.asyncio
async def test_the_example_writes_its_readout_like_any_other_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The example is the reference, so it must be complete, not merely green."""
    _set_env(monkeypatch)

    response = await _post_contract()

    written = {item["role"]: item["uri"] for item in response.json()["outputs"]}
    assert written[READOUT_OUTPUT_ROLE] == _READOUT_URI
