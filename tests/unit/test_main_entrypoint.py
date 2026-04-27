"""Tests for the __main__ entry point dispatch logic."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from grabatus_service_core.__main__ import (
    EntryPointError,
    run_worker_once,
)
from grabatus_service_core.errors import ComputeError
from grabatus_service_core.runner import ExecutionResult


def _ok_result() -> ExecutionResult[Any]:
    return ExecutionResult(
        request_id=UUID("11111111-1111-1111-1111-111111111111"),
        status="ok",
        contract=None,
        receipts=None,
        error=None,
        metadata={},
        webhook_ack=None,
    )


def _err_result() -> ExecutionResult[Any]:
    return ExecutionResult(
        request_id=UUID("00000000-0000-0000-0000-000000000000"),
        status="error",
        contract=None,
        receipts=None,
        error=ComputeError("boom"),
        metadata={},
        webhook_ack=None,
    )


def test_run_worker_once_returns_zero_on_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = MagicMock()
    runner.execute.return_value = _ok_result()

    contract = json.dumps({"some": "payload"}).encode("utf-8")
    monkeypatch.setenv("GBT_JOB_PAYLOAD", contract.decode("utf-8"))
    monkeypatch.setenv("GBT_JOB_REQUEST_ID", "11111111-1111-1111-1111-111111111111")

    exit_code = run_worker_once(runner=runner)

    assert exit_code == 0


def test_run_worker_once_returns_nonzero_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = MagicMock()
    runner.execute.return_value = _err_result()
    monkeypatch.setenv("GBT_JOB_PAYLOAD", "{}")
    monkeypatch.setenv("GBT_JOB_REQUEST_ID", "00000000-0000-0000-0000-000000000000")

    exit_code = run_worker_once(runner=runner)

    assert exit_code == 1


def test_run_worker_once_raises_when_payload_env_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GBT_JOB_PAYLOAD", raising=False)
    runner = MagicMock()

    with pytest.raises(EntryPointError, match="GBT_JOB_PAYLOAD"):
        run_worker_once(runner=runner)
