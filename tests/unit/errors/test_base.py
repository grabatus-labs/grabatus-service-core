"""Tests for the base error class."""

from __future__ import annotations

import pytest

from grabatus_service_core.errors.base import GrabatusServiceError


class _SampleError(GrabatusServiceError):
    error_code = "sample_error"
    http_status = 200
    retriable = False


def test_grabatus_service_error_has_error_code_classvar() -> None:
    assert _SampleError.error_code == "sample_error"


def test_grabatus_service_error_has_http_status_classvar() -> None:
    assert _SampleError.http_status == 200


def test_grabatus_service_error_has_retriable_classvar() -> None:
    assert _SampleError.retriable is False


def test_grabatus_service_error_message_is_passed_through() -> None:
    err = _SampleError("something failed at boundary")
    assert str(err) == "something failed at boundary"


def test_grabatus_service_error_context_defaults_to_empty_dict() -> None:
    err = _SampleError("msg")
    assert err.context == {}


def test_grabatus_service_error_context_is_stored() -> None:
    ctx = {"input_uri": "gs://bucket/key", "tenant": "grabatus"}
    err = _SampleError("msg", context=ctx)
    assert err.context == ctx


def test_grabatus_service_error_is_an_exception() -> None:
    with pytest.raises(GrabatusServiceError):
        raise _SampleError("boom")


def test_grabatus_service_error_subclass_must_declare_error_code() -> None:
    """Concrete subclasses must declare error_code; base class is abstract."""
    with pytest.raises(NotImplementedError, match="error_code"):
        GrabatusServiceError("msg")
