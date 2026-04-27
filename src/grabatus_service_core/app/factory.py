"""build_app: assemble a FastAPI instance around a ServiceRunner."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI

from grabatus_service_core.app.exception_handler import register_exception_handlers
from grabatus_service_core.app.middleware import install_request_context_middleware
from grabatus_service_core.app.routes import make_router

if TYPE_CHECKING:
    from grabatus_service_core.contract.base import ParamsT
    from grabatus_service_core.ports.observability import ObservabilityPort
    from grabatus_service_core.runner import ServiceRunner


def build_app(
    *,
    runner: ServiceRunner[ParamsT],
    observability: ObservabilityPort,
) -> FastAPI:
    """Return a fully wired FastAPI app bound to the supplied runner."""
    app = FastAPI(title="grabatus-service-core", version="0.1.0")
    app.state.runner = runner
    app.state.observability = observability
    install_request_context_middleware(app)
    app.include_router(make_router())
    register_exception_handlers(app)
    return app
