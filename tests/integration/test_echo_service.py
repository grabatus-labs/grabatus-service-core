"""End-to-end smoke test for the echo example service."""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx
import pytest
from examples.echo_service import build


@pytest.mark.xfail(
    strict=True,
    reason="Issue #11: EchoComputeBackend emits no model_readout, and ModelFamily "
    "has no value that honestly describes a passthrough service. Pending the "
    "decision recorded there.",
)
@pytest.mark.asyncio
async def test_echo_service_runs_end_to_end_via_asgi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GBT_RUNTIME_MODE", "monolith")
    monkeypatch.setenv("GBT_ENV", "local")
    monkeypatch.setenv("SERVICE_SECRET_KEY", "test-secret")
    monkeypatch.setenv("GBT_ALLOWED_SCHEMES", "inline,https")

    app = build()

    contract: dict[str, Any] = {
        "envelope": {
            "protocol_version": "1.0",
            "request_id": "11111111-1111-1111-1111-111111111111",
            "created_at": "2026-04-26T00:00:00Z",
            "origin": "internal",
        },
        "identity": {"user_id": "999", "tenant_id": "grabatus"},
        "references": {"parameter_id": "p", "result_id": "r"},
        "service": {"name": "echo", "version": "0.0.1"},
        "inputs": [
            {
                "role": "payload",
                "source_uri": "inline://hello",
                "format": "inline",
                "format_hints": {"format": "inline"},
            },
        ],
        "outputs": [
            {
                "role": "echoed",
                "destination_uri": "inline://echoed",
                "format": "inline",
                "format_hints": {"format": "inline"},
                "compression": "none",
                "write_mode": "overwrite",
            },
        ],
        "callback": {
            "url": "https://example.com/cb",
            "auth_scheme": "jwt_hs256",
        },
        "parameters": {},
    }

    pubsub = {
        "message": {
            "data": base64.b64encode(json.dumps(contract).encode("utf-8")).decode(
                "ascii",
            ),
            "messageId": "1",
        },
        "subscription": "x",
    }

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        response = await client.post("/run_service", json=pubsub)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["request_id"] == "11111111-1111-1111-1111-111111111111"
