"""SharedReceiverRunner: value objects (execute body added in next task)."""

from uuid import uuid4

import pytest

from grabatus_service_core.receiver.runner import (
    ReceiverExecutionResult,
)


def test_receiver_execution_result_holds_status_and_request_id() -> None:
    rid = uuid4()
    result = ReceiverExecutionResult(
        request_id=rid,
        status="ok",
        dispatched_job_id="job-123",
        error=None,
    )
    assert result.request_id == rid
    assert result.status == "ok"
    assert result.dispatched_job_id == "job-123"
    assert result.error is None


def test_receiver_execution_result_is_frozen() -> None:
    result = ReceiverExecutionResult(
        request_id=uuid4(),
        status="ok",
        dispatched_job_id="j",
        error=None,
    )
    with pytest.raises((AttributeError, TypeError)):
        result.status = "error"  # type: ignore[misc]
