"""HTTP routes for grabatus_service_core."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Request

from grabatus_service_core.ports.values import RawMessage

if TYPE_CHECKING:
    from grabatus_service_core.errors import GrabatusServiceError


def make_router() -> APIRouter:
    """Return an APIRouter exposing /run_service and /health/live."""
    router = APIRouter()

    @router.get("/health/live")
    def _health_live() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/health/ready")
    def _health_ready(request: Request) -> dict[str, str]:
        runner = request.app.state.runner
        return {"status": "ready", "mode": runner.mode.value}

    @router.post("/run_service")
    async def _run_service(request: Request) -> dict[str, Any]:
        raw_bytes = await request.body()
        runner = request.app.state.runner
        result = runner.execute(RawMessage(payload=raw_bytes))
        return _result_to_json(result)

    return router


def _result_to_json(result: object) -> dict[str, Any]:
    body: dict[str, Any] = {
        "status": result.status,  # type: ignore[attr-defined]
        "request_id": str(result.request_id),  # type: ignore[attr-defined]
    }
    error = getattr(result, "error", None)
    if error is not None:
        body["error"] = _error_to_json(error)
    receipts = getattr(result, "receipts", None)
    if receipts is not None:
        body["outputs"] = [
            {"role": role, "uri": r.uri, "bytes_written": r.bytes_written}
            for role, r in receipts.by_role.items()
        ]
    metadata = getattr(result, "metadata", None)
    if metadata:
        body["metadata"] = dict(metadata)
    webhook_ack = getattr(result, "webhook_ack", None)
    if webhook_ack is not None:
        body["webhook_ack"] = {
            "http_status": webhook_ack.http_status,
            "response_body": webhook_ack.response_body,
        }
    dispatched_job_id = getattr(result, "dispatched_job_id", None)
    if dispatched_job_id is not None:
        body["dispatched_job_id"] = dispatched_job_id
    return body


def _error_to_json(error: GrabatusServiceError) -> dict[str, Any]:
    return {
        "error_code": error.error_code,
        "message": str(error),
    }
