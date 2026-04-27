"""HTTP routes for grabatus_service_core."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Request

from grabatus_service_core.ports.values import RawMessage

if TYPE_CHECKING:
    from grabatus_service_core.errors import GrabatusServiceError
    from grabatus_service_core.runner import ExecutionResult


def make_router() -> APIRouter:
    """Return an APIRouter exposing /run_service and /health/live."""
    router = APIRouter()

    @router.get("/health/live")
    def _health_live() -> dict[str, str]:
        return {"status": "ok"}

    @router.post("/run_service")
    async def _run_service(request: Request) -> dict[str, Any]:
        raw_bytes = await request.body()
        runner = request.app.state.runner
        result: ExecutionResult[Any] = runner.execute(RawMessage(payload=raw_bytes))
        return _result_to_json(result)

    return router


def _result_to_json(result: ExecutionResult[Any]) -> dict[str, Any]:
    body: dict[str, Any] = {
        "status": result.status,
        "request_id": str(result.request_id),
    }
    if result.error is not None:
        body["error"] = _error_to_json(result.error)
    if result.receipts is not None:
        body["outputs"] = [
            {"role": role, "uri": r.uri, "bytes_written": r.bytes_written}
            for role, r in result.receipts.by_role.items()
        ]
    if result.metadata:
        body["metadata"] = dict(result.metadata)
    if result.webhook_ack is not None:
        body["webhook_ack"] = {
            "http_status": result.webhook_ack.http_status,
            "response_body": result.webhook_ack.response_body,
        }
    return body


def _error_to_json(error: GrabatusServiceError) -> dict[str, Any]:
    return {
        "error_code": error.error_code,
        "message": str(error),
    }
