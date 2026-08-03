"""Forecast service builder."""

from __future__ import annotations

from typing import TYPE_CHECKING

from examples.forecast_service.compute import (
    MovingAverageBackend,
    MovingAverageParameters,
)
from grabatus_service_core.adapters.message_pubsub import PubSubMessagePort
from grabatus_service_core.bootstrap import build_monolith_app
from grabatus_service_core.contract.base import BaseServiceContract
from grabatus_service_core.settings import Settings
from grabatus_service_core.testing import (
    AllowAllPolicy,
    InMemoryJobDispatcher,
    InMemorySecretsAdapter,
    InMemoryStorage,
    NullObservability,
    RecordingWebhookNotifier,
)

if TYPE_CHECKING:
    from fastapi import FastAPI


# The backend ignores its inputs — the point of the example is the readout,
# not the arithmetic — but the contract still declares one, so storage has
# to serve it.
_INLINE_PAYLOAD = b"week,units\n2026-06-01,120\n"


def build() -> FastAPI:
    settings = Settings()  # type: ignore[call-arg]  # pydantic-settings reads env
    storage = InMemoryStorage(
        seed={"gs://gbt-storage-grabatus/user_999/history.csv": _INLINE_PAYLOAD},
    )
    return build_monolith_app(
        settings=settings,
        contract_type=BaseServiceContract[MovingAverageParameters],
        compute=MovingAverageBackend(),
        adapters={
            "storage": storage,
            "message": PubSubMessagePort(),
            "webhook": RecordingWebhookNotifier(),
            "secrets": InMemorySecretsAdapter(seed={}),
            "authorizer": AllowAllPolicy(),
            "observability": NullObservability(),
            "job_dispatcher": InMemoryJobDispatcher(),
        },
    )
