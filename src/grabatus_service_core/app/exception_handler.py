"""Global FastAPI exception handlers for grabatus_service_core.

Translates every exception escaping a route into a 200-OK response so
Pub/Sub push acks. Typed ``GrabatusServiceError`` carries its declared
``error_code``; everything else is collapsed to ``internal_error`` and
the original message is dropped from the response body to avoid leaking
internals to the platform webhook.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse

from grabatus_service_core.errors import GrabatusServiceError

if TYPE_CHECKING:
    from fastapi import FastAPI, Request


_INTERNAL_ERROR_CODE = "internal_error"
_INTERNAL_ERROR_MESSAGE = "internal server error"


def register_exception_handlers(app: FastAPI) -> None:
    """Attach Grabatus-aware exception handlers to ``app``."""

    @app.exception_handler(GrabatusServiceError)
    async def _handle_grabatus_error(
        request: Request,
        exc: GrabatusServiceError,
    ) -> JSONResponse:
        observability = request.app.state.observability
        observability.log(
            "service_error",
            error_code=exc.error_code,
            message=str(exc),
            path=request.url.path,
        )
        return JSONResponse(
            status_code=200,
            content={
                "status": "error",
                "error": {"error_code": exc.error_code, "message": str(exc)},
            },
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        observability = request.app.state.observability
        observability.log(
            "internal_error",
            exception_type=type(exc).__name__,
            exception_message=str(exc),
            path=request.url.path,
        )
        return JSONResponse(
            status_code=200,
            content={
                "status": "error",
                "error": {
                    "error_code": _INTERNAL_ERROR_CODE,
                    "message": _INTERNAL_ERROR_MESSAGE,
                },
            },
        )
