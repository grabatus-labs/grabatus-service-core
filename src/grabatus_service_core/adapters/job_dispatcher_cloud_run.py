"""CloudRunJobsDispatcher: trigger Cloud Run Jobs executions for the worker."""

from __future__ import annotations

from typing import TYPE_CHECKING

from google.api_core import exceptions as gcp_exceptions
from google.cloud import run_v2

from grabatus_service_core.adapters.retry import with_retry
from grabatus_service_core.errors import ComputeError
from grabatus_service_core.ports.job_dispatcher import DispatchedJob

if TYPE_CHECKING:
    from uuid import UUID


_PAYLOAD_ENV_VAR = "GBT_JOB_PAYLOAD"
_REQUEST_ID_ENV_VAR = "GBT_JOB_REQUEST_ID"
_RETRIABLE_CLOUD_RUN_ERRORS: tuple[type[BaseException], ...] = (
    gcp_exceptions.ServiceUnavailable,
    gcp_exceptions.InternalServerError,
    gcp_exceptions.GatewayTimeout,
    gcp_exceptions.DeadlineExceeded,
    gcp_exceptions.TooManyRequests,
    ConnectionError,
)


class CloudRunJobsDispatcher:
    """Dispatch worker runs by triggering a Cloud Run Job execution.

    The Cloud Run Jobs API client is constructed lazily on first
    ``dispatch()`` so the receiver process can start in environments without GCP
    credentials (e.g. local Docker smoke tests, CI builds).

    The job binary expects two env-var overrides on each invocation:
    ``GBT_JOB_PAYLOAD`` (the contract bytes, base64-decoded by the worker)
    and ``GBT_JOB_REQUEST_ID`` (for log correlation).
    """

    def __init__(
        self,
        *,
        project_id: str,
        region: str,
        client: run_v2.JobsClient | None = None,
    ) -> None:
        self._project_id = project_id
        self._region = region
        self._client: run_v2.JobsClient | None = client  # ready if injected

    def _get_client(self) -> run_v2.JobsClient:
        if self._client is None:
            self._client = run_v2.JobsClient()
        return self._client

    @with_retry(retry_on=_RETRIABLE_CLOUD_RUN_ERRORS)
    def dispatch(
        self,
        *,
        job_name: str,
        payload: bytes,
        request_id: UUID,
    ) -> DispatchedJob:
        full_job_name = f"projects/{self._project_id}/locations/{self._region}/jobs/{job_name}"
        overrides = run_v2.RunJobRequest.Overrides(
            container_overrides=[
                run_v2.RunJobRequest.Overrides.ContainerOverride(
                    env=[
                        run_v2.EnvVar(
                            name=_PAYLOAD_ENV_VAR,
                            value=payload.decode("utf-8"),
                        ),
                        run_v2.EnvVar(
                            name=_REQUEST_ID_ENV_VAR,
                            value=str(request_id),
                        ),
                    ],
                ),
            ],
        )
        request = run_v2.RunJobRequest(name=full_job_name, overrides=overrides)
        try:
            operation = self._get_client().run_job(request=request)
        except _RETRIABLE_CLOUD_RUN_ERRORS:
            raise
        except gcp_exceptions.GoogleAPIError as exc:
            raise ComputeError(
                f"CloudRunJobsDispatcher: run_job failed for job_name={full_job_name!r}: {exc}",
            ) from exc
        return DispatchedJob(job_id=operation.metadata.name, request_id=request_id)
