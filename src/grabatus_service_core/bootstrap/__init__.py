"""High-level helpers that compose Settings → adapters → runner → app."""

from grabatus_service_core.bootstrap.factories import (
    build_monolith_app,
    build_receiver_app,
    build_worker_runner,
)

__all__ = [
    "build_monolith_app",
    "build_receiver_app",
    "build_worker_runner",
]
