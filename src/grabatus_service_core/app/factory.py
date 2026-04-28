"""build_app: assemble a FastAPI instance around any runner with .execute() and .mode."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from fastapi import FastAPI

from grabatus_service_core.app.exception_handler import register_exception_handlers
from grabatus_service_core.app.middleware import install_request_context_middleware
from grabatus_service_core.app.routes import make_router

if TYPE_CHECKING:
    from grabatus_service_core.ports.observability import ObservabilityPort
    from grabatus_service_core.ports.values import RawMessage


@runtime_checkable
class RunnerLike(Protocol):
    """Anything build_app can wrap.

    Both ``ServiceRunner[ParamsT]`` and ``SharedReceiverRunner`` satisfy
    this Protocol. The runner must expose:

    - ``execute(raw: RawMessage) -> object`` returning a result with at
      least ``status``, ``request_id``, and ``error`` attributes.
    - ``mode`` exposing a ``.value: str`` (used by ``/health/ready``).
    """

    @property
    def mode(self) -> object: ...

    def execute(self, raw: RawMessage) -> object: ...


def build_app(
    *,
    runner: RunnerLike,
    observability: ObservabilityPort,
) -> FastAPI:
    """Return a fully wired FastAPI app bound to the supplied runner."""
    app = FastAPI(title="grabatus-service-core", version="0.2.0")
    app.state.runner = runner
    app.state.observability = observability
    install_request_context_middleware(app)
    app.include_router(make_router())
    register_exception_handlers(app)
    return app
