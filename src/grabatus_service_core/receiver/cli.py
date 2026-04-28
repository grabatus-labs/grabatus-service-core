"""Entry point invoked by the ``grabatus-receiver`` console script."""

from __future__ import annotations

import os

import uvicorn

from grabatus_service_core.adapters.clock import SystemClock
from grabatus_service_core.adapters.job_dispatcher_cloud_run import (
    CloudRunJobsDispatcher,
)
from grabatus_service_core.adapters.message_pubsub import PubSubMessagePort
from grabatus_service_core.adapters.observability_otel import (
    OpenTelemetryObservability,
)
from grabatus_service_core.observability.otel_setup import setup_opentelemetry
from grabatus_service_core.receiver.app import build_shared_receiver_app
from grabatus_service_core.receiver.runner import SharedReceiverAdapters
from grabatus_service_core.security.tenant_prefix_policy import TenantPrefixPolicy
from grabatus_service_core.settings import Settings


def main() -> None:
    """Read env-driven Settings, build adapters and the FastAPI app, run uvicorn.

    Required env vars:
    - ``GBT_RUNTIME_MODE``, ``GBT_ENV``, ``SERVICE_SECRET_KEY`` (Settings)
    - ``GBT_GCP_PROJECT`` (no default — must be set)
    - ``GBT_SERVICE_REGISTRY`` (e.g. ``forecast:grabatus-forecasting-worker``)

    Optional:
    - ``GBT_GCP_REGION`` (defaults ``us-east1``)
    - ``GBT_BUCKET_PREFIX`` (defaults ``gbt-storage``)
    - ``PORT`` (defaults ``8080``)
    """
    settings = Settings()  # type: ignore[call-arg]  # pydantic-settings reads env vars
    if settings.gcp_project is None:
        raise ValueError(
            "GBT_GCP_PROJECT must be set when running the shared receiver",
        )

    otel_handle = setup_opentelemetry(
        env=settings.env,
        sample_rate=settings.trace_sample_rate,
    )
    adapters = SharedReceiverAdapters(
        message=PubSubMessagePort(),
        authorizer=TenantPrefixPolicy(bucket_prefix=settings.bucket_prefix),
        job_dispatcher=CloudRunJobsDispatcher(
            project_id=settings.gcp_project,
            region=settings.gcp_region,
        ),
        observability=OpenTelemetryObservability(
            tracer=otel_handle.tracer,
            meter=otel_handle.meter,
        ),
        clock=SystemClock(),
    )
    app = build_shared_receiver_app(settings=settings, adapters=adapters)
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)  # noqa: S104  # nosec B104 — Cloud Run requires 0.0.0.0
