"""Tests for SystemClock and the with_retry decorator."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import pytest

from grabatus_service_core.adapters.clock import SystemClock
from grabatus_service_core.adapters.retry import with_retry
from grabatus_service_core.ports.clock import ClockPort


def test_system_clock_satisfies_clock_port() -> None:
    assert isinstance(SystemClock(), ClockPort)


def test_system_clock_now_is_aware_utc() -> None:
    clock = SystemClock()
    before = datetime.now(tz=UTC)
    value = clock.now()
    after = datetime.now(tz=UTC)

    assert value.tzinfo is UTC
    assert before - timedelta(seconds=1) <= value <= after + timedelta(seconds=1)


def test_system_clock_monotonic_does_not_decrease() -> None:
    clock = SystemClock()
    a = clock.monotonic()
    time.sleep(0.001)
    b = clock.monotonic()

    assert b >= a


def test_with_retry_calls_function_until_it_succeeds() -> None:
    attempts: list[int] = []

    @with_retry(retry_on=(RuntimeError,), max_attempts=3, initial_backoff=0.001)
    def flaky() -> str:
        attempts.append(1)
        if len(attempts) < 2:
            raise RuntimeError("transient")
        return "ok"

    assert flaky() == "ok"
    assert len(attempts) == 2


def test_with_retry_re_raises_after_exhausting_attempts() -> None:
    attempts: list[int] = []

    @with_retry(retry_on=(RuntimeError,), max_attempts=2, initial_backoff=0.001)
    def always_fails() -> str:
        attempts.append(1)
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError, match="nope"):
        always_fails()
    assert len(attempts) == 2


def test_with_retry_does_not_retry_unlisted_exceptions() -> None:
    attempts: list[int] = []

    @with_retry(retry_on=(RuntimeError,), max_attempts=3, initial_backoff=0.001)
    def raises_value_error() -> str:
        attempts.append(1)
        raise ValueError("not retriable")

    with pytest.raises(ValueError, match="not retriable"):
        raises_value_error()
    assert len(attempts) == 1
