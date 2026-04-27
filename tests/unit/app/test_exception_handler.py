"""Tests for the FastAPI global exception handler."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from grabatus_service_core.app.exception_handler import register_exception_handlers
from grabatus_service_core.errors import InvalidContractError
from grabatus_service_core.testing import NullObservability


def _app_that_raises(exc: Exception) -> FastAPI:
    app = FastAPI()
    app.state.observability = NullObservability()
    register_exception_handlers(app)

    @app.get("/boom")
    def _boom() -> None:
        raise exc

    return app


def test_handler_translates_grabatus_error_to_200_with_error_payload() -> None:
    app = _app_that_raises(InvalidContractError("missing field x"))
    client = TestClient(app)

    response = client.get("/boom")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "status": "error",
        "error": {"error_code": "invalid_contract", "message": "missing field x"},
    }


def test_handler_translates_unexpected_exception_to_200_with_internal_code() -> None:
    app = _app_that_raises(RuntimeError("kaboom"))
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/boom")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["error_code"] == "internal_error"
    assert "kaboom" not in body["error"]["message"]
