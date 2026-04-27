"""Shared receiver: stateless front door for all Grabatus computational services."""

from __future__ import annotations

from grabatus_service_core.receiver.registry import ServiceRegistry
from grabatus_service_core.receiver.runner import (
    ReceiverExecutionResult,
    SharedReceiverAdapters,
    SharedReceiverRunner,
)

__all__ = [
    "ReceiverExecutionResult",
    "ServiceRegistry",
    "SharedReceiverAdapters",
    "SharedReceiverRunner",
    "build_shared_receiver_app",
]


def __getattr__(name: str) -> object:
    if name == "build_shared_receiver_app":
        from grabatus_service_core.receiver.app import build_shared_receiver_app  # noqa: PLC0415

        return build_shared_receiver_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
