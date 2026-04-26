"""Tests for CloudRunJobsDispatcher (mock the Cloud Run Jobs client)."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import UUID

import pytest
from google.api_core import exceptions as gcp_exceptions

from grabatus_service_core.adapters.job_dispatcher_cloud_run import (
    CloudRunJobsDispatcher,
)
from grabatus_service_core.errors import ComputeError
from grabatus_service_core.ports.job_dispatcher import JobDispatcherPort

_RID = UUID("a3f9c21e-bf38-4e75-9a2f-c89b6c3f2d12")


def _client_returning(operation_name: str = "operations/abc") -> MagicMock:
    operation = MagicMock()
    operation.metadata.name = operation_name
    client = MagicMock()
    client.run_job.return_value = operation
    return client


def _dispatcher(client: MagicMock) -> CloudRunJobsDispatcher:
    return CloudRunJobsDispatcher(project_id="grabatus", region="us-east1", client=client)


def test_cloud_run_dispatcher_satisfies_port() -> None:
    assert isinstance(_dispatcher(MagicMock()), JobDispatcherPort)


def test_cloud_run_dispatcher_returns_dispatched_job() -> None:
    client = _client_returning("projects/grabatus/operations/op-1")
    dispatcher = _dispatcher(client)

    job = dispatcher.dispatch(
        job_name="forecast-worker",
        payload=b'{"x":1}',
        request_id=_RID,
    )

    assert job.job_id == "projects/grabatus/operations/op-1"
    assert job.request_id == _RID

    request = client.run_job.call_args.kwargs["request"]
    assert request.name == ("projects/grabatus/locations/us-east1/jobs/forecast-worker")


def test_cloud_run_dispatcher_translates_api_error() -> None:
    client = MagicMock()
    client.run_job.side_effect = gcp_exceptions.Forbidden("denied")
    dispatcher = _dispatcher(client)

    with pytest.raises(ComputeError, match="run_job failed"):
        dispatcher.dispatch(job_name="forecast", payload=b"x", request_id=_RID)


def test_cloud_run_dispatcher_retries_on_transient_error() -> None:
    operation = MagicMock()
    operation.metadata.name = "ok"
    client = MagicMock()
    client.run_job.side_effect = [
        gcp_exceptions.ServiceUnavailable("503"),
        operation,
    ]
    dispatcher = _dispatcher(client)

    job = dispatcher.dispatch(job_name="forecast", payload=b"x", request_id=_RID)

    assert job.job_id == "ok"
    assert client.run_job.call_count == 2
