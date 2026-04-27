"""Tests for the request-id contextvar middleware."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from grabatus_service_core.app.middleware import (
    REQUEST_ID_HEADER,
    install_request_context_middleware,
    request_id_var,
)
from grabatus_service_core.testing import NullObservability


def _build_test_app() -> tuple[FastAPI, list[str | None]]:
    app = FastAPI()
    app.state.observability = NullObservability()
    install_request_context_middleware(app)
    seen: list[str | None] = []

    @app.get("/probe")
    def _probe(request: Request) -> dict[str, Any]:
        seen.append(request_id_var.get())
        return {"request_id": request_id_var.get()}

    return app, seen


def test_middleware_generates_request_id_when_header_absent() -> None:
    app, seen = _build_test_app()
    client = TestClient(app)

    response = client.get("/probe")

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] is not None
    assert seen[0] is not None


def test_middleware_uses_incoming_header_when_present() -> None:
    app, seen = _build_test_app()
    client = TestClient(app)

    response = client.get(
        "/probe",
        headers={REQUEST_ID_HEADER: "11111111-2222-3333-4444-555555555555"},
    )

    assert response.json()["request_id"] == "11111111-2222-3333-4444-555555555555"
    assert seen[0] == "11111111-2222-3333-4444-555555555555"


def test_middleware_echoes_request_id_in_response_header() -> None:
    app, _seen = _build_test_app()
    client = TestClient(app)

    response = client.get(
        "/probe",
        headers={REQUEST_ID_HEADER: "abc123"},
    )

    assert response.headers[REQUEST_ID_HEADER] == "abc123"


def test_middleware_resets_contextvar_after_request() -> None:
    app, _seen = _build_test_app()
    client = TestClient(app)
    client.get("/probe", headers={REQUEST_ID_HEADER: "xyz"})

    assert request_id_var.get() is None
