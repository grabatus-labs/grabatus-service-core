"""build_shared_receiver_app: FastAPI factory for the shared receiver."""

from __future__ import annotations

from typing import TYPE_CHECKING

from grabatus_service_core.app import build_app
from grabatus_service_core.receiver.runner import (
    SharedReceiverAdapters,
    SharedReceiverRunner,
)
from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist

if TYPE_CHECKING:
    from fastapi import FastAPI

    from grabatus_service_core.settings import Settings


def build_shared_receiver_app(
    *,
    settings: Settings,
    adapters: SharedReceiverAdapters,
) -> FastAPI:
    """Wire a FastAPI app around a ``SharedReceiverRunner``.

    Example:
        >>> from grabatus_service_core.adapters.message_pubsub import PubSubMessagePort
        >>> from grabatus_service_core.testing import (
        ...     AllowAllPolicy, FrozenClock, InMemoryJobDispatcher, NullObservability,
        ... )
        >>> settings = Settings()  # reads env vars
        >>> adapters = SharedReceiverAdapters(
        ...     message=PubSubMessagePort(),
        ...     authorizer=AllowAllPolicy(),
        ...     job_dispatcher=InMemoryJobDispatcher(),
        ...     observability=NullObservability(),
        ...     clock=FrozenClock(iso_string="2026-04-27T12:00:00Z"),
        ... )
        >>> app = build_shared_receiver_app(settings=settings, adapters=adapters)
    """
    runner = SharedReceiverRunner(
        adapters=adapters,
        scheme_allowlist=SchemeAllowlist(allowed=set(settings.allowed_schemes)),
        registry=settings.service_registry,
    )
    return build_app(runner=runner, observability=adapters.observability)
