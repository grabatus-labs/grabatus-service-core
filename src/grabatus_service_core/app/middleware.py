"""Request-scoped context middleware: request_id contextvar + header echo.

Every request enters a fresh ``contextvars.Token`` so concurrent requests
under uvicorn/Starlette cannot leak state across each other. The handler
echoes the request_id back to the caller so the platform can correlate
its own logs without parsing the response body.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastapi import FastAPI
    from starlette.requests import Request
    from starlette.responses import Response


REQUEST_ID_HEADER = "x-request-id"
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind a request-scoped UUID to ``request_id_var`` for the request lifetime."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming or str(uuid.uuid4())
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def install_request_context_middleware(app: FastAPI) -> None:
    """Attach :class:`RequestContextMiddleware` to ``app``."""
    app.add_middleware(RequestContextMiddleware)
