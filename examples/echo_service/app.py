"""Echo service builder."""

from __future__ import annotations

from typing import TYPE_CHECKING

from examples.echo_service.compute import EchoComputeBackend, EchoParameters
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


_INLINE_PAYLOAD = b"hello-bytes"


def build() -> FastAPI:
    settings = Settings()  # type: ignore[call-arg]  # pydantic-settings reads env
    storage = InMemoryStorage(seed={"inline://hello": _INLINE_PAYLOAD})
    return build_monolith_app(
        settings=settings,
        contract_type=BaseServiceContract[EchoParameters],
        compute=EchoComputeBackend(),
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
